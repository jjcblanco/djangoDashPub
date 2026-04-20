"""
scalping_strategies.py
======================
Tres estrategias de scalping para timeframes cortos (1m-15m) en Binance.
Cada estrategia recibe un DataFrame OHLCV con indicadores ya calculados
y devuelve un dict con la señal, precios de SL/TP, y snapshot de indicadores.
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


# ──────────────────────────────────────────────
# ESTRATEGIA 1: EMA CROSS (5/20) + VOLUMEN
# ──────────────────────────────────────────────

def strategy_ema_cross(df: pd.DataFrame, sl_atr_mult=1.5, tp_atr_mult=2.5, params=None) -> dict:
    """
    EMA 5 cruza EMA 20 con confirmación de volumen elevado.

    Condiciones LONG:
      - EMA5 cruza por encima de EMA20 (cruce en la última vela)
      - Volumen actual > Media de volumen (20p)
      - RSI entre 40 y 65 (evitar sobrecompra)

    Condiciones SHORT:
      - EMA5 cruza por debajo de EMA20
      - Volumen actual > Media de volumen (20p)
      - RSI entre 35 y 60
    """
    params = params or {}
    fast = params.get('ema_fast', 5)
    slow = params.get('ema_slow', 20)
    vol_period = params.get('vol_period', 20)
    rsi_period = params.get('rsi_period', 14)

    if len(df) < slow + 5:
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
    vol_ok  = float(cur['volume'])  > float(cur['vol_ma']) * 1.1 if not pd.isna(cur['vol_ma']) else False

    snapshot = {
        'ema_fast': round(float(cur['ema_fast']), 8),
        'ema_slow': round(float(cur['ema_slow']), 8),
        'rsi': round(rsi_val, 2),
        'volume_ratio': round(float(cur['volume']) / float(cur['vol_ma']), 2) if not pd.isna(cur['vol_ma']) else None,
        'atr': round(atr_val, 8),
    }

    # Cruce alcista
    cross_up   = (prev['ema_fast'] <= prev['ema_slow']) and (cur['ema_fast'] > cur['ema_slow'])
    # Cruce bajista
    cross_down = (prev['ema_fast'] >= prev['ema_slow']) and (cur['ema_fast'] < cur['ema_slow'])

    if cross_up and vol_ok and 40 <= rsi_val <= 68:
        confidence = 0.55 + (0.15 if vol_ok else 0) + (0.10 if rsi_val < 60 else 0)
        sl, tp = _calc_sl_tp(price, 'BUY', atr_val, sl_atr_mult, tp_atr_mult)
        return {'signal': 'BUY', 'entry': price, 'sl': sl, 'tp': tp,
                'confidence': round(min(confidence, 0.95), 2), 'indicators': snapshot}

    if cross_down and vol_ok and 32 <= rsi_val <= 60:
        confidence = 0.55 + (0.15 if vol_ok else 0) + (0.10 if rsi_val > 40 else 0)
        sl, tp = _calc_sl_tp(price, 'SELL', atr_val, sl_atr_mult, tp_atr_mult)
        return {'signal': 'SELL', 'entry': price, 'sl': sl, 'tp': tp,
                'confidence': round(min(confidence, 0.95), 2), 'indicators': snapshot}

    return _no_signal()


# ──────────────────────────────────────────────
# ESTRATEGIA 2: BOLLINGER SQUEEZE + MOMENTUM
# ──────────────────────────────────────────────

def strategy_bb_squeeze(df: pd.DataFrame, sl_atr_mult=1.5, tp_atr_mult=2.5, params=None) -> dict:
    """
    Detecta compresión de Bollinger Bands (squeeze) y opera el breakout.

    Condiciones:
      - BB Width en el percentil 20 más bajo de las últimas 50 velas (squeeze)
      - Precio rompe la banda superior → LONG
      - Precio rompe la banda inferior → SHORT
      - MACD Histograma confirma dirección
    """
    params = params or {}
    bb_period  = params.get('bb_period', 20)
    bb_std     = params.get('bb_std', 2.0)
    squeeze_pct = params.get('squeeze_pct', 20)  # percentil

    if len(df) < bb_period + 10:
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

    # ¿El precio rompe la banda ahora DESPUÉS del squeeze?
    breakout_up   = in_squeeze_prev and (float(cur['close']) > float(cur['bb_upper']))
    breakout_down = in_squeeze_prev and (float(cur['close']) < float(cur['bb_lower']))

    # Confirmación MACD
    macd_bull = float(cur['macd_hist']) > 0 and float(cur['macd_hist']) > float(prev['macd_hist'])
    macd_bear = float(cur['macd_hist']) < 0 and float(cur['macd_hist']) < float(prev['macd_hist'])

    snapshot = {
        'bb_upper':   round(float(cur['bb_upper']), 8),
        'bb_lower':   round(float(cur['bb_lower']), 8),
        'bb_width':   round(float(cur['bb_width']), 6),
        'width_threshold': round(float(width_threshold), 6),
        'in_squeeze_prev': in_squeeze_prev,
        'macd_hist':  round(float(cur['macd_hist']), 8),
        'atr':        round(atr_val, 8),
    }

    if breakout_up and macd_bull:
        confidence = 0.60 + (0.20 if macd_bull else 0)
        sl, tp = _calc_sl_tp(price, 'BUY', atr_val, sl_atr_mult, tp_atr_mult)
        return {'signal': 'BUY', 'entry': price, 'sl': sl, 'tp': tp,
                'confidence': round(min(confidence, 0.95), 2), 'indicators': snapshot}

    if breakout_down and macd_bear:
        confidence = 0.60 + (0.20 if macd_bear else 0)
        sl, tp = _calc_sl_tp(price, 'SELL', atr_val, sl_atr_mult, tp_atr_mult)
        return {'signal': 'SELL', 'entry': price, 'sl': sl, 'tp': tp,
                'confidence': round(min(confidence, 0.95), 2), 'indicators': snapshot}

    return _no_signal()


# ──────────────────────────────────────────────
# ESTRATEGIA 3: VWAP + RSI BOUNCE
# ──────────────────────────────────────────────

def strategy_vwap_rsi(df: pd.DataFrame, sl_atr_mult=1.2, tp_atr_mult=2.0, params=None) -> dict:
    """
    Rebote en VWAP con confirmación de RSI en zona extrema.

    Condiciones LONG:
      - Precio toca o cruza VWAP desde abajo
      - RSI < 38 y subiendo (rebote desde sobreventa)
      - Vela actual alcista (close > open)

    Condiciones SHORT:
      - Precio toca o cruza VWAP desde arriba
      - RSI > 62 y bajando (rebote desde sobrecompra)
      - Vela actual bajista (close < open)
    """
    params = params or {}
    rsi_period    = params.get('rsi_period', 14)
    rsi_oversold  = params.get('rsi_oversold', 38)
    rsi_overbought= params.get('rsi_overbought', 62)

    if len(df) < 30:
        return _no_signal()

    df = _prepare_df(df)
    df['vwap']    = vwap(df)
    df['rsi']     = calculate_rsi(df, rsi_period)
    df['atr_val'] = atr(df, 14)

    cur  = df.iloc[-1]
    prev = df.iloc[-2]

    price   = float(cur['close'])
    vwap_v  = float(cur['vwap'])   if not pd.isna(cur['vwap'])   else price
    rsi_cur = float(cur['rsi'])    if not pd.isna(cur['rsi'])    else 50
    rsi_prv = float(prev['rsi'])   if not pd.isna(prev['rsi'])   else 50
    atr_val = float(cur['atr_val'])if not pd.isna(cur['atr_val'])else price * 0.003

    # Cruce de VWAP
    cross_above = (float(prev['close']) <= float(prev['vwap'])) and (price > vwap_v)  # precio cruza VWAP hacia arriba
    cross_below = (float(prev['close']) >= float(prev['vwap'])) and (price < vwap_v)  # precio cruza VWAP hacia abajo

    bullish_candle = float(cur['close']) > float(cur['open'])
    bearish_candle = float(cur['close']) < float(cur['open'])
    rsi_rising  = rsi_cur > rsi_prv
    rsi_falling = rsi_cur < rsi_prv

    snapshot = {
        'vwap':  round(vwap_v, 8),
        'price': round(price, 8),
        'price_vs_vwap_pct': round((price - vwap_v) / vwap_v * 100, 3),
        'rsi':   round(rsi_cur, 2),
        'rsi_prev': round(rsi_prv, 2),
        'atr':   round(atr_val, 8),
    }

    if cross_above and rsi_cur < rsi_oversold and rsi_rising and bullish_candle:
        confidence = 0.50 + (0.20 if rsi_cur < 32 else 0.10) + (0.10 if bullish_candle else 0)
        sl, tp = _calc_sl_tp(price, 'BUY', atr_val, sl_atr_mult, tp_atr_mult)
        return {'signal': 'BUY', 'entry': price, 'sl': sl, 'tp': tp,
                'confidence': round(min(confidence, 0.95), 2), 'indicators': snapshot}

    if cross_below and rsi_cur > rsi_overbought and rsi_falling and bearish_candle:
        confidence = 0.50 + (0.20 if rsi_cur > 68 else 0.10) + (0.10 if bearish_candle else 0)
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
                 sl_atr_mult: float = 1.5, tp_atr_mult: float = 2.5,
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
