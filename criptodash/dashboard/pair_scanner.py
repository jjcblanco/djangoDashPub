"""
pair_scanner.py
===============
Scanner de pares de Binance para detectar oportunidades de scalping.
Puntúa cada par por volatilidad, volumen, tendencia y señales activas,
y devuelve un ranking con la estrategia recomendada.
"""
import logging
import time
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

# Pares default a escanear si no se quieren todos
DEFAULT_PAIRS = [
    'BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT',
    'DOGE/USDT', 'XRP/USDT', 'ADA/USDT', 'AVAX/USDT',
    'LINK/USDT', 'DOT/USDT', 'MATIC/USDT', 'LTC/USDT',
    'SHIB/USDT', 'PEPE/USDT', 'WIF/USDT', 'INJ/USDT',
    'ARB/USDT', 'OP/USDT', 'SUI/USDT', 'APT/USDT',
    'NEAR/USDT', 'FIL/USDT', 'ATOM/USDT', 'UNI/USDT',
]

# Parámetros de scoring
VOLATILITY_MIN_PCT = 0.20   # ATR% mínimo — muy baja vol no sirve para scalp
VOLATILITY_MAX_PCT = 3.00   # ATR% máximo — demasiado caótico
VOLUME_MIN_USDT    = 500_000  # Volumen 24h mínimo en USDT


def _get_exchange():
    """Obtiene instancia de Binance via CCXT."""
    try:
        import ccxt
        from decouple import config
        api_key = config('BINANCE_APIKEY', default='')
        secret  = config('BINANCE_SECRET', default='')
        
        if not api_key or not secret:
            logger.error("[PairScanner] BINANCE_APIKEY o BINANCE_SECRET no están configurados en .env")
            return None

        exchange = ccxt.binance({
            'apiKey':  api_key,
            'secret':  secret,
            'enableRateLimit': True,
            'options': {'defaultType': 'spot'},
        })
        return exchange
    except Exception as e:
        logger.error(f'[PairScanner] Error crítico iniciando CCXT: {e}')
        return None


def fetch_ohlcv_df(exchange, symbol: str, timeframe: str, limit: int = 100) -> pd.DataFrame | None:
    """Descarga velas OHLCV y devuelve DataFrame. Retorna None si falla."""
    try:
        raw = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        if not raw:
            return None
        df = pd.DataFrame(raw, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = pd.to_numeric(df[col])
        return df
    except Exception as e:
        logger.warning(f'[PairScanner] Error OHLCV {symbol}: {e}')
        return None


def score_volatility(atr_pct: float) -> float:
    """0-100: Penaliza si la volatilidad es muy baja o muy alta."""
    if atr_pct < VOLATILITY_MIN_PCT:
        return max(0, atr_pct / VOLATILITY_MIN_PCT * 50)
    if atr_pct > VOLATILITY_MAX_PCT:
        return max(0, 100 - (atr_pct - VOLATILITY_MAX_PCT) * 20)
    # Zona ideal: entre 0.3% y 1.5% → score 70-100
    ideal_pct = 1.0
    distance  = abs(atr_pct - ideal_pct)
    return max(60, 100 - distance * 25)


def score_volume(volume_24h_usdt: float) -> float:
    """0-100: Mayor volumen = mejor liquidez para scalping."""
    if volume_24h_usdt < VOLUME_MIN_USDT:
        return 0
    # Log scale normalizado
    import math
    score = min(100, math.log10(volume_24h_usdt / VOLUME_MIN_USDT) * 30 + 50)
    return round(score, 1)


def score_trend(adx_val: float) -> float:
    """0-100: ADX mide fuerza de tendencia. Ideal >25."""
    if adx_val is None:
        return 50
    if adx_val < 15:
        return 20   # Ranging, peor para scalp direccional
    if adx_val < 25:
        return 50
    if adx_val < 40:
        return 80
    return 95       # Tendencia muy fuerte


def score_signals(signals: list) -> float:
    """0-100: Más señales confluentes = mayor score."""
    n = len(signals)
    if n == 0:
        return 0
    if n == 1:
        return 40
    if n == 2:
        return 70
    return 95


def recommend_strategy(df: pd.DataFrame, signals: list) -> str:
    """Elige la mejor estrategia basada en condiciones actuales."""
    strategy_votes = {}
    for s in signals:
        strat = s.get('strategy', '')
        strategy_votes[strat] = strategy_votes.get(strat, 0) + s.get('confidence', 0)

    if strategy_votes:
        return max(strategy_votes, key=strategy_votes.get)

    # Fallback por condiciones de mercado
    try:
        from .indicadores import adx as calc_adx, atr
        adx_series = calc_adx(df, 14)
        adx_val    = float(adx_series.iloc[-1]) if not adx_series.empty else 0

        atr_series = atr(df, 14)
        atr_val    = float(atr_series.iloc[-1]) if not atr_series.empty else 0
        atr_pct    = (atr_val / float(df['close'].iloc[-1])) * 100 if float(df['close'].iloc[-1]) > 0 else 0

        if adx_val > 30:
            return 'EMA_CROSS'     # Tendencia fuerte → cruce de medias
        if atr_pct < 0.5:
            return 'BB_SQUEEZE'    # Baja vol → esperar squeeze
        return 'VWAP_RSI'          # Default: rebote VWAP
    except Exception:
        return 'EMA_CROSS'


def scan_pair(exchange, symbol: str, timeframe: str, run_signals: bool = True) -> dict | None:
    """
    Analiza un par y devuelve su resultado de scan.
    Retorna None si no hay datos suficientes.
    """
    try:
        from .indicadores import atr as calc_atr, adx as calc_adx
        from .scalping_strategies import run_strategy

        # Obtener OHLCV
        df = fetch_ohlcv_df(exchange, symbol, timeframe, limit=120)
        if df is None or len(df) < 50:
            return None

        price = float(df['close'].iloc[-1])
        if price <= 0:
            return None

        # Calcular ATR%
        atr_series = calc_atr(df, 14)
        atr_val    = float(atr_series.iloc[-1]) if not atr_series.empty else 0
        atr_pct    = (atr_val / price) * 100

        # ADX
        try:
            adx_series = calc_adx(df, 14)
            adx_val    = float(adx_series.iloc[-1]) if not adx_series.empty else None
        except Exception:
            adx_val = None

        # Volumen 24h aproximado (últimas 288 velas de 5m = 24h)
        vol_24h = float(df['volume'].tail(288).sum() * price)

        # Scores
        vol_score   = score_volatility(atr_pct)
        volume_scr  = score_volume(vol_24h)
        trend_scr   = score_trend(adx_val)

        # Señales activas
        signals = []
        if run_signals:
            for strat_name in ['EMA_CROSS', 'BB_SQUEEZE', 'VWAP_RSI']:
                try:
                    result = run_strategy(strat_name, df)
                    if result['signal']:
                        signals.append({
                            'strategy':   strat_name,
                            'signal':     result['signal'],
                            'confidence': result['confidence'],
                            'sl':         result['sl'],
                            'tp':         result['tp'],
                        })
                except Exception as e:
                    logger.debug(f'[PairScanner] {symbol} {strat_name}: {e}')

        signal_scr = score_signals(signals)

        # Score total ponderado
        total = round(
            vol_score  * 0.25 +
            volume_scr * 0.25 +
            trend_scr  * 0.25 +
            signal_scr * 0.25,
            1
        )

        return {
            'symbol':               symbol,
            'price':                price,
            'atr_pct':              round(atr_pct, 4),
            'volume_24h_usdt':      round(vol_24h, 0),
            'adx_value':            round(adx_val, 2) if adx_val else None,
            'volatility_score':     round(vol_score,  1),
            'volume_score':         round(volume_scr, 1),
            'trend_score':          round(trend_scr,  1),
            'signal_score':         round(signal_scr, 1),
            'total_score':          total,
            'signals_found':        signals,
            'recommended_strategy': recommend_strategy(df, signals),
        }

    except Exception as e:
        logger.error(f'[PairScanner] Error analizando {symbol}: {e}')
        return None


def scan_all_pairs(
    timeframe: str = '5m',
    symbols: list  = None,
    top_n: int     = 15,
    run_signals: bool = True,
) -> list:
    """
    Escanea todos los pares indicados y devuelve el top N rankeado por total_score.

    Args:
        timeframe:    Timeframe de análisis ('1m', '3m', '5m', '15m')
        symbols:      Lista de símbolos. Si None, usa DEFAULT_PAIRS.
        top_n:        Cuántos pares retornar
        run_signals:  Si debe evaluar las 3 estrategias (más lento pero más completo)

    Returns:
        Lista de dicts ordenada por total_score desc
    """
    exchange = _get_exchange()
    if exchange is None:
        return []

    symbols = symbols or DEFAULT_PAIRS
    results = []

    for symbol in symbols:
        result = scan_pair(exchange, symbol, timeframe, run_signals)
        if result:
            results.append(result)
        time.sleep(0.15)  # Respetar rate limit de Binance

    results.sort(key=lambda x: x['total_score'], reverse=True)
    return results[:top_n]


def save_scan_results(results: list, timeframe: str = '5m'):
    """
    Persiste los resultados del scan en la BD.
    Crea o actualiza registros PairScanResult y ScalpAlert para señales encontradas.
    """
    from .models import PairScanResult, Pair, ScalpAlert
    from django.utils import timezone
    from datetime import timedelta

    for r in results:
        symbol = r['symbol']

        # Obtener o crear el Pair en BD
        pair_obj, _ = Pair.objects.get_or_create(
            symbol=symbol,
            defaults={
                'base_asset':  symbol.split('/')[0],
                'quote_asset': symbol.split('/')[1] if '/' in symbol else 'USDT',
                'exchange':    'binance',
            }
        )

        # Guardar resultado del scan
        PairScanResult.objects.create(
            pair                 = pair_obj,
            timeframe            = timeframe,
            volatility_score     = r['volatility_score'],
            volume_score         = r['volume_score'],
            trend_score          = r['trend_score'],
            signal_score         = r['signal_score'],
            total_score          = r['total_score'],
            current_price        = r['price'],
            atr_pct              = r['atr_pct'],
            volume_24h_usdt      = r['volume_24h_usdt'],
            adx_value            = r['adx_value'],
            signals_found        = r['signals_found'],
            recommended_strategy = r['recommended_strategy'],
        )

        # Crear ScalpAlerts para señales encontradas
        for sig in r.get('signals_found', []):
            confidence = sig.get('confidence', 0)
            if confidence < 0.45:   # Bajado de 0.55 → más señales visibles
                continue   # Ignorar señales muy débiles

            # Evitar duplicados en los últimos 5 minutos
            recent = ScalpAlert.objects.filter(
                pair        = pair_obj,
                strategy    = sig['strategy'],
                signal_type = sig['signal'],
                created_at__gte = timezone.now() - timedelta(minutes=5),
            ).exists()
            if recent:
                continue

            ScalpAlert.objects.create(
                pair             = pair_obj,
                timeframe        = timeframe,
                strategy         = sig['strategy'],
                signal_type      = sig['signal'],
                price_at_alert   = r['price'],
                suggested_sl     = sig.get('sl'),
                suggested_tp     = sig.get('tp'),
                confidence       = confidence,
                indicators_snapshot = sig,
                expires_at       = timezone.now() + timedelta(minutes=15),
            )

    logger.info(f'[PairScanner] {len(results)} resultados guardados en BD.')
