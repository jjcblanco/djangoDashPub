"""
scalping_strategies.py
======================
Tres estrategias de scalping para timeframes cortos (1m-15m) en Binance.
Cada estrategia recibe un DataFrame OHLCV con indicadores ya calculados
y devuelve un dict con la señal, precios de SL/TP, y snapshot de indicadores.

MEJORAS v2:
  - Filtro de tendencia global: EMA 200 (solo operar a favor de la tendencia mayor)
  - Filtro de mercado lateral: ADX > 20 (no operar en rangos sin dirección)
  - VWAP intradiario real (resetea cada día, no acumulado del histórico)
  - Ajuste de ratio TP/SL a 1:1.5 por defecto (más realista para timeframes cortos)
"""
import pandas as pd
import numpy as np
from .indicadores import (
    calculate_rsi, macd, atr, vwap, obv, adx,
    bollinger_bands, volume_ma, ema,
)


# ──────────────────────────────────────────────
# UTILIDADES COMPARTIDAS
# ──────────────────────────────────────────────

def _prepare_df(df: pd.DataFrame, extra_cols: list = None) -> pd.DataFrame:
    """Garantiza columnas mínimas y tipos correctos."""
    required = ['open', 'high', 'low', 'close', 'volume']
    df = df.copy()
    for col in required:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    df.dropna(subset=required, inplace=True)
    return df


def _no_signal():
    return {'signal': None, 'entry': None, 'sl': None, 'tp': None, 'confidence': 0.0, 'indicators': {}}


def _calc_sl_tp(price: float, side: str, atr_val: float, sl_mult: float, tp_mult: float):
    """Calcula SL y TP basados en ATR."""
    if side == 'BUY':
        sl = round(price - atr_val * sl_mult, 8)
        tp = round(price + atr_val * tp_mult, 8)
    else:
        sl = round(price + atr_val * sl_mult, 8)
        tp = round(price - atr_val * tp_mult, 8)
    return sl, tp


def _vwap_intraday(df: pd.DataFrame) -> pd.Series:
    """
    MEJORA #3: VWAP intradiario real.
    Resetea el cálculo al inicio de cada día UTC en vez de acumular
    todo el historial (que daría un nivel irrelevante para scalping).
    """
    df = df.copy()
    # Intentar usar el índice como datetime; si no tiene timestamp, caer al VWAP clásico
    if 'timestamp' in df.columns:
        try:
            df['_dt'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
        except Exception:
            df['_dt'] = pd.to_datetime(df['timestamp'], utc=True)
    elif isinstance(df.index, pd.DatetimeIndex):
        df['_dt'] = df.index
    else:
        # Sin información de tiempo → usar VWAP clásico
        v = df['volume']
        p = (df['high'] + df['low'] + df['close']) / 3
        return (p * v).cumsum() / v.cumsum()

    df['_date'] = df['_dt'].dt.date
    df['_tp']   = (df['high'] + df['low'] + df['close']) / 3
    df['_tpv']  = df['_tp'] * df['volume']

    df['_cum_tpv'] = df.groupby('_date')['_tpv'].cumsum()
    df['_cum_vol'] = df.groupby('_date')['volume'].cumsum()
    return df['_cum_tpv'] / df['_cum_vol']


def _trend_filters(df: pd.DataFrame, adx_threshold: int = 20):
    """
    MEJORAS #1 y #2: EMA 200 + ADX.
    Devuelve (trend_up, trend_down, trend_strong).
      - trend_up:     precio sobre EMA200 (tendencia alcista mayor)
      - trend_down:   precio bajo EMA200 (tendencia bajista mayor)
      - trend_strong: ADX > threshold (mercado en movimiento, no lateral)
    """
    cur = df.iloc[-1]

    # EMA 200 (si hay menos velas se relaja el filtro)
    ema200 = df['close'].ewm(span=200, adjust=False).mean()
    ema200_val = float(ema200.iloc[-1])
    price = float(cur['close'])

    trend_up   = price > ema200_val
    trend_down = price < ema200_val

    # ADX
    adx_series = adx(df, 14)
    adx_val    = float(adx_series.iloc[-1]) if not pd.isna(adx_series.iloc[-1]) else 0
    trend_strong = adx_val > adx_threshold

    return bool(trend_up), bool(trend_down), bool(trend_strong), round(adx_val, 2), round(ema200_val, 8)


# ──────────────────────────────────────────────
# ESTRATEGIA 1: EMA CROSS (5/20) + VOLUMEN
# ──────────────────────────────────────────────

def strategy_ema_cross(df: pd.DataFrame, sl_atr_mult=2.2, tp_atr_mult=1.6, params=None) -> dict:
    """
    EMA 5 cruza EMA 20 con confirmación de volumen elevado.

    Mejoras v2:
      - Solo LONG si precio > EMA200 (tendencia alcista mayor).
      - Solo SHORT si precio < EMA200 (tendencia bajista mayor).
      - Solo opera si ADX > 20 (mercado con dirección).
      - TP reducido a 2.0× ATR (vs 2.5 anterior) para mayor tasa de éxito.

    Condiciones LONG:
      - EMA5 cruza por encima de EMA20 (cruce en la última vela)
      - Volumen actual > Media de volumen (20p)
      - RSI entre 40 y 65 (evitar sobrecompra)
      - Precio por encima de EMA200
      - ADX > 20

    Condiciones SHORT:
      - EMA5 cruza por debajo de EMA20
      - Volumen actual > Media de volumen (20p)
      - RSI entre 35 y 60
      - Precio por debajo de EMA200
      - ADX > 20
    """
    params = params or {}
    fast = params.get('ema_fast', 5)
    slow = params.get('ema_slow', 20)
    vol_period = params.get('vol_period', 20)
    rsi_period = params.get('rsi_period', 14)
    adx_threshold = params.get('adx_threshold', 20)

    if len(df) < max(slow + 5, 205):   # necesitamos velas para EMA200
        return _no_signal()

    df = _prepare_df(df)

    # Calcular indicadores
    df['ema_fast'] = df['close'].ewm(span=fast, adjust=False).mean()
    df['ema_slow'] = df['close'].ewm(span=slow, adjust=False).mean()
    df['rsi']      = calculate_rsi(df, rsi_period)
    df['vol_ma']   = df['volume'].rolling(vol_period).mean()
    df['atr_val']  = atr(df, 14)

    cur  = df.iloc[-1]
    prev = df.iloc[-2]

    price   = float(cur['close'])
    atr_val = float(cur['atr_val']) if not pd.isna(cur['atr_val']) else price * 0.003
    rsi_val = float(cur['rsi'])     if not pd.isna(cur['rsi'])     else 50
    vol_ok  = bool(float(cur['volume']) > float(cur['vol_ma']) * 1.1) if not pd.isna(cur['vol_ma']) else False

    # MEJORAS #1 y #2: filtros de tendencia y ADX
    trend_up, trend_down, trend_strong, adx_val, ema200_val = _trend_filters(df, adx_threshold)

    snapshot = {
        'ema_fast':     round(float(cur['ema_fast']), 8),
        'ema_slow':     round(float(cur['ema_slow']), 8),
        'ema200':       ema200_val,
        'rsi':          round(rsi_val, 2),
        'adx':          adx_val,
        'volume_ratio': round(float(cur['volume']) / float(cur['vol_ma']), 2) if not pd.isna(cur['vol_ma']) else None,
        'atr':          round(atr_val, 8),
        'trend_up':     trend_up,
        'trend_strong': trend_strong,
    }

    # Cruce alcista
    cross_up   = bool(float(prev['ema_fast']) <= float(prev['ema_slow'])) and bool(float(cur['ema_fast']) > float(cur['ema_slow']))
    # Cruce bajista
    cross_down = bool(float(prev['ema_fast']) >= float(prev['ema_slow'])) and bool(float(cur['ema_fast']) < float(cur['ema_slow']))

    if cross_up and vol_ok and 40 <= rsi_val <= 68 and trend_up and trend_strong:
        confidence = 0.65 + (0.10 if vol_ok else 0) + (0.10 if rsi_val < 60 else 0) + (0.10 if adx_val > 25 else 0)
        sl, tp = _calc_sl_tp(price, 'BUY', atr_val, sl_atr_mult, tp_atr_mult)
        return {'signal': 'BUY', 'entry': price, 'sl': sl, 'tp': tp,
                'confidence': round(min(confidence, 0.95), 2), 'indicators': snapshot}

    if cross_down and vol_ok and 32 <= rsi_val <= 60 and trend_down and trend_strong:
        confidence = 0.65 + (0.10 if vol_ok else 0) + (0.10 if rsi_val > 40 else 0) + (0.10 if adx_val > 25 else 0)
        sl, tp = _calc_sl_tp(price, 'SELL', atr_val, sl_atr_mult, tp_atr_mult)
        return {'signal': 'SELL', 'entry': price, 'sl': sl, 'tp': tp,
                'confidence': round(min(confidence, 0.95), 2), 'indicators': snapshot}

    return _no_signal()


# ──────────────────────────────────────────────
# ESTRATEGIA 2: BOLLINGER SQUEEZE + MOMENTUM
# ──────────────────────────────────────────────

def strategy_bb_squeeze(df: pd.DataFrame, sl_atr_mult=2.2, tp_atr_mult=1.6, params=None) -> dict:
    """
    Detecta compresión de Bollinger Bands (squeeze) y opera el breakout.

    Mejoras v2:
      - Solo opera si ADX > 20 (los breakouts en rangos son trampas).
      - Filtro de tendencia mayor: solo LONG si precio > EMA200, solo SHORT si < EMA200.
      - TP reducido a 2.0× ATR para mayor frecuencia de acierto.

    Condiciones:
      - BB Width en el percentil 20 más bajo de las últimas 50 velas (squeeze)
      - Precio rompe la banda superior → LONG (solo si tendencia alcista)
      - Precio rompe la banda inferior → SHORT (solo si tendencia bajista)
      - MACD Histograma confirma dirección
      - ADX > 20
    """
    params = params or {}
    bb_period   = params.get('bb_period', 20)
    bb_std      = params.get('bb_std', 2.0)
    squeeze_pct = params.get('squeeze_pct', 20)
    adx_threshold = params.get('adx_threshold', 20)

    if len(df) < max(bb_period + 10, 205):
        return _no_signal()

    df = _prepare_df(df)
    df = bollinger_bands(df, window=bb_period, num_std=bb_std, generate_signals=False)
    df = macd(df)
    df['atr_val'] = atr(df, 14)

    cur  = df.iloc[-1]
    prev = df.iloc[-2]

    price   = float(cur['close'])
    atr_val = float(cur['atr_val']) if not pd.isna(cur['atr_val']) else price * 0.003

    # Ancho normalizado de las bandas
    bb_width_series = df['bb_width'].dropna()
    if len(bb_width_series) < 10:
        return _no_signal()

    width_threshold = float(bb_width_series.quantile(squeeze_pct / 100))
    in_squeeze_prev = bool(float(prev['bb_width']) < width_threshold) if not pd.isna(prev['bb_width']) else False

    # Confirmacion de volumen (evita falsos breakouts)
    df['vol_ma'] = df['volume'].rolling(20).mean()
    vol_cur = float(cur['volume'])
    vol_avg = float(cur['vol_ma']) if not pd.isna(cur['vol_ma']) else vol_cur
    vol_surge = vol_cur > vol_avg * 1.3   # volumen 30%+ por encima de la media

    # Confirmacion MACD
    macd_bull = bool(float(cur['macd_hist']) > 0 and float(cur['macd_hist']) > float(prev['macd_hist']))
    macd_bear = bool(float(cur['macd_hist']) < 0 and float(cur['macd_hist']) < float(prev['macd_hist']))

    # MEJORAS #1 y #2: filtros de tendencia y ADX
    trend_up, trend_down, trend_strong, adx_val, ema200_val = _trend_filters(df, adx_threshold)

    snapshot = {
        'bb_upper':        round(float(cur['bb_upper']), 8),
        'bb_lower':        round(float(cur['bb_lower']), 8),
        'bb_width':        round(float(cur['bb_width']), 6),
        'width_threshold': round(float(width_threshold), 6),
        'in_squeeze_prev': in_squeeze_prev,
        'macd_hist':       round(float(cur['macd_hist']), 8),
        'atr':             round(atr_val, 8),
        'adx':             adx_val,
        'ema200':          ema200_val,
        'trend_up':        trend_up,
        'trend_strong':    trend_strong,
        'vol_surge':       vol_surge,
    }

    if breakout_up and macd_bull and vol_surge and trend_up and trend_strong:
        confidence = 0.60 + (0.10 if macd_bull else 0) + (0.05 if adx_val > 25 else 0)
        sl, tp = _calc_sl_tp(price, 'BUY', atr_val, sl_atr_mult, tp_atr_mult)
        return {'signal': 'BUY', 'entry': price, 'sl': sl, 'tp': tp,
                'confidence': round(min(confidence, 0.75), 2), 'indicators': snapshot}

    if breakout_down and macd_bear and vol_surge and trend_down and trend_strong:
        confidence = 0.60 + (0.10 if macd_bear else 0) + (0.05 if adx_val > 25 else 0)
        sl, tp = _calc_sl_tp(price, 'SELL', atr_val, sl_atr_mult, tp_atr_mult)
        return {'signal': 'SELL', 'entry': price, 'sl': sl, 'tp': tp,
                'confidence': round(min(confidence, 0.75), 2), 'indicators': snapshot}

    return _no_signal()


# ──────────────────────────────────────────────
# ESTRATEGIA 3: VWAP + RSI BOUNCE
# ──────────────────────────────────────────────

def strategy_vwap_rsi(df: pd.DataFrame, sl_atr_mult=2.2, tp_atr_mult=1.6, params=None) -> dict:
    """
    Rebote en VWAP con confirmación de RSI en zona extrema.

    Mejoras v2:
      - VWAP intradiario real (resetea por día UTC, no acumulado desde siempre).
      - Filtro de tendencia mayor (EMA 200).
      - Filtro ADX > 20.
      - TP reducido de 2.0 a 1.8× ATR para timeframes cortos.

    Condiciones LONG:
      - Precio cruza VWAP desde abajo
      - RSI < 40 y subiendo (rebote desde sobreventa)
      - Vela actual alcista (close > open)
      - Precio en tendencia alcista mayor (EMA200)
      - ADX > 20

    Condiciones SHORT:
      - Precio cruza VWAP desde arriba
      - RSI > 60 y bajando (rebote desde sobrecompra)
      - Vela actual bajista (close < open)
      - Precio en tendencia bajista mayor (EMA200)
      - ADX > 20
    """
    params = params or {}
    rsi_period     = params.get('rsi_period', 14)
    rsi_oversold   = params.get('rsi_oversold', 40)
    rsi_overbought = params.get('rsi_overbought', 60)
    adx_threshold  = params.get('adx_threshold', 20)

    if len(df) < max(30, 205):
        return _no_signal()

    df = _prepare_df(df)

    # MEJORA #3: VWAP intradiario real
    df['vwap']    = _vwap_intraday(df)
    df['rsi']     = calculate_rsi(df, rsi_period)
    df['atr_val'] = atr(df, 14)

    cur  = df.iloc[-1]
    prev = df.iloc[-2]

    price   = float(cur['close'])
    vwap_v  = float(cur['vwap'])    if not pd.isna(cur['vwap'])    else price
    rsi_cur = float(cur['rsi'])     if not pd.isna(cur['rsi'])     else 50
    rsi_prv = float(prev['rsi'])    if not pd.isna(prev['rsi'])    else 50
    atr_val = float(cur['atr_val']) if not pd.isna(cur['atr_val']) else price * 0.003

    prev_close = float(prev['close'])
    prev_vwap  = float(prev['vwap']) if not pd.isna(prev['vwap']) else prev_close

    # Cruce de VWAP
    cross_above = bool(prev_close <= prev_vwap) and bool(price > vwap_v)
    cross_below = bool(prev_close >= prev_vwap) and bool(price < vwap_v)

    bullish_candle = bool(float(cur['close']) > float(cur['open']))
    bearish_candle = bool(float(cur['close']) < float(cur['open']))
    rsi_rising     = bool(rsi_cur > rsi_prv)
    rsi_falling    = bool(rsi_cur < rsi_prv)

    # MEJORAS #1 y #2: filtros de tendencia y ADX
    trend_up, trend_down, trend_strong, adx_val, ema200_val = _trend_filters(df, adx_threshold)

    snapshot = {
        'vwap':             round(vwap_v, 8),
        'price':            round(price, 8),
        'price_vs_vwap_pct': round((price - vwap_v) / vwap_v * 100, 3) if vwap_v else 0,
        'rsi':              round(rsi_cur, 2),
        'rsi_prev':         round(rsi_prv, 2),
        'atr':              round(atr_val, 8),
        'adx':              adx_val,
        'ema200':           ema200_val,
        'trend_up':         trend_up,
        'trend_strong':     trend_strong,
    }

    if cross_above and rsi_cur < rsi_oversold and rsi_rising and bullish_candle and trend_up and trend_strong:
        confidence = 0.60 + (0.10 if rsi_cur < 32 else 0.05) + (0.05 if bullish_candle else 0) + (0.05 if adx_val > 25 else 0)
        sl, tp = _calc_sl_tp(price, 'BUY', atr_val, sl_atr_mult, tp_atr_mult)
        return {'signal': 'BUY', 'entry': price, 'sl': sl, 'tp': tp,
                'confidence': round(min(confidence, 0.80), 2), 'indicators': snapshot}

    if cross_below and rsi_cur > rsi_overbought and rsi_falling and bearish_candle and trend_down and trend_strong:
        confidence = 0.60 + (0.10 if rsi_cur > 68 else 0.05) + (0.05 if bearish_candle else 0) + (0.05 if adx_val > 25 else 0)
        sl, tp = _calc_sl_tp(price, 'SELL', atr_val, sl_atr_mult, tp_atr_mult)
        return {'signal': 'SELL', 'entry': price, 'sl': sl, 'tp': tp,
                'confidence': round(min(confidence, 0.95), 2), 'indicators': snapshot}

    return _no_signal()


# ──────────────────────────────────────────────
# DISPATCHER: elige estrategia y ejecuta
# ──────────────────────────────────────────────

STRATEGIES = {
    'EMA_CROSS':  strategy_ema_cross,
    'BB_SQUEEZE': strategy_bb_squeeze,
    'VWAP_RSI':   strategy_vwap_rsi,
}


def run_strategy(strategy_name: str, df: pd.DataFrame,
                 sl_atr_mult: float = 2.2, tp_atr_mult: float = 1.6,
                 params: dict = None) -> dict:
    """Ejecuta la estrategia indicada y devuelve el resultado."""
    fn = STRATEGIES.get(strategy_name)
    if fn is None:
        return _no_signal()
    try:
        return fn(df, sl_atr_mult=sl_atr_mult, tp_atr_mult=tp_atr_mult, params=params)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f'[ScalpStrategy] {strategy_name} error: {e}')
        return _no_signal()
