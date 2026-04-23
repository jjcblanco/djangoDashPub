"""
Whale Intelligence - Fase 1: Captura de Contexto de Mercado.

Cuando una ballena hace un trade, este módulo captura un snapshot
de los indicadores técnicos del activo en ese momento.
Esto genera el dataset para aprender de las condiciones en que operan.
"""

import ccxt
import pandas as pd
import numpy as np
import time
from django.conf import settings

# Instancia global para reutilizar conexiones
_BINANCE_EXCHANGE = None

def _get_binance():
    """Obtiene una instancia de ccxt.binance sin API key (solo datos públicos)."""
    global _BINANCE_EXCHANGE
    if _BINANCE_EXCHANGE is None:
        _BINANCE_EXCHANGE = ccxt.binance({
            'options': {'adjustForTimeDifference': True},
            'enableRateLimit': True,
            'timeout': 10000, # 10 segundos
        })
    return _BINANCE_EXCHANGE

# Cache simple en memoria para evitar llamadas redundantes en el mismo ciclo de sync
# {symbol: (timestamp, data)}
_CONTEXT_CACHE = {}
_CACHE_TTL = 300  # 5 minutos

# Duración en ms por timeframe (para calcular cuántas velas pedir)
_TIMEFRAME_MS = {
    '1h':  3_600_000,
    '4h': 14_400_000,
    '1d': 86_400_000,
}


def fetch_market_context(symbol, timeframe='4h', limit=100):
    """
    Captura un snapshot de indicadores técnicos para un token.
    
    Args:
        symbol: Símbolo del token (ej: 'BTC', 'ETH', 'SOL')
        timeframe: Temporalidad de las velas ('1h', '4h', '1d')
        limit: Cantidad de velas a obtener
    
    Returns:
        dict con indicadores o None si falla
    """
    symbol_upper = symbol.upper().strip()
    
    # 1. Verificar Cache
    now = time.time()
    if symbol_upper in _CONTEXT_CACHE:
        ts, data = _CONTEXT_CACHE[symbol_upper]
        if now - ts < _CACHE_TTL:
            return data

    # Ignorar stablecoins (no tienen indicadores útiles)
    if symbol_upper in ('USDC', 'USDT', 'DAI', 'BUSD', 'FDUSD'):
        return None
    
    pair = f"{symbol_upper}/USDT"
    
    try:
        exchange = _get_binance()
        ohlcv = exchange.fetch_ohlcv(pair, timeframe=timeframe, limit=limit)
        
        if not ohlcv or len(ohlcv) < 30:
            return None
        
        # Crear DataFrame
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        
        # Calcular indicadores usando la librería existente
        context = _calculate_indicators(df)
        context['pair'] = pair
        context['timeframe'] = timeframe
        context['candles_used'] = len(df)
        
        # Guardar en Cache
        _CONTEXT_CACHE[symbol_upper] = (now, context)
        
        return context
        
    except ccxt.BadSymbol:
        # Par no existe en Binance (token nuevo o de nicho)
        return None
    except ccxt.NetworkError as e:
        print(f"[Whale Intelligence] Network error for {symbol}: {e}")
        return None
    except Exception as e:
        print(f"[Whale Intelligence] Error fetching context for {symbol}: {e}")
        return None


def _calculate_indicators(df):
    """Calcula todos los indicadores sobre un DataFrame de velas."""
    
    last = df.iloc[-1]
    close = float(last['close'])
    
    # ═══ RSI(14) ═══
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    rsi_series = 100 - (100 / (1 + rs))
    rsi_val = float(rsi_series.iloc[-1]) if not pd.isna(rsi_series.iloc[-1]) else None
    
    # ═══ MACD(12, 26, 9) ═══
    ema12 = df['close'].ewm(span=12, adjust=False).mean()
    ema26 = df['close'].ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    histogram = macd_line - signal_line
    
    macd_val = float(macd_line.iloc[-1]) if not pd.isna(macd_line.iloc[-1]) else None
    macd_signal_val = float(signal_line.iloc[-1]) if not pd.isna(signal_line.iloc[-1]) else None
    macd_hist_val = float(histogram.iloc[-1]) if not pd.isna(histogram.iloc[-1]) else None
    
    # ═══ SMAs ═══
    sma50 = float(df['close'].rolling(50).mean().iloc[-1]) if len(df) >= 50 else None
    sma200 = float(df['close'].rolling(200).mean().iloc[-1]) if len(df) >= 200 else None
    
    price_vs_sma50 = round(((close - sma50) / sma50) * 100, 2) if sma50 else None
    price_vs_sma200 = round(((close - sma200) / sma200) * 100, 2) if sma200 else None
    
    # ═══ Bollinger Bands(20, 2) ═══
    bb_middle = df['close'].rolling(20).mean()
    bb_std = df['close'].rolling(20).std()
    bb_upper = bb_middle + (bb_std * 2)
    bb_lower = bb_middle - (bb_std * 2)
    
    bb_pos = None
    if not pd.isna(bb_upper.iloc[-1]) and not pd.isna(bb_lower.iloc[-1]):
        bb_range = float(bb_upper.iloc[-1]) - float(bb_lower.iloc[-1])
        if bb_range > 0:
            bb_pos = round((close - float(bb_lower.iloc[-1])) / bb_range, 3)
    
    # ═══ Volumen vs VolMA(20) ═══
    vol_ma20 = df['volume'].rolling(20).mean()
    vol_ratio = None
    if not pd.isna(vol_ma20.iloc[-1]) and float(vol_ma20.iloc[-1]) > 0:
        vol_ratio = round(float(last['volume']) / float(vol_ma20.iloc[-1]), 2)
    
    # ═══ Supertrend simplificado (en uptrend?) ═══
    hl2 = (df['high'] + df['low']) / 2
    atr14 = df['high'].sub(df['low']).rolling(14).mean()
    upper_band = hl2 + (3 * atr14)
    in_uptrend = close > float(upper_band.iloc[-2]) if len(df) > 1 and not pd.isna(upper_band.iloc[-2]) else None
    
    # ═══ ATR (volatilidad) ═══
    atr_val = float(atr14.iloc[-1]) if not pd.isna(atr14.iloc[-1]) else None
    atr_pct = round((atr_val / close) * 100, 2) if atr_val and close > 0 else None
    
    # ═══ Velas previas (contexto de acción del precio) ═══
    recent_closes = df['close'].tail(4).tolist()
    consecutive_red = 0
    for i in range(len(recent_closes) - 1, 0, -1):
        if recent_closes[i] < recent_closes[i - 1]:
            consecutive_red += 1
        else:
            break
    
    return {
        'price': round(close, 6),
        'rsi_14': round(rsi_val, 2) if rsi_val is not None else None,
        'macd': round(macd_val, 6) if macd_val is not None else None,
        'macd_signal': round(macd_signal_val, 6) if macd_signal_val is not None else None,
        'macd_hist': round(macd_hist_val, 6) if macd_hist_val is not None else None,
        'macd_cross': 'bullish' if (macd_val is not None and macd_signal_val is not None and macd_val > macd_signal_val) else 'bearish',
        'sma_50': round(sma50, 4) if sma50 is not None else None,
        'sma_200': round(sma200, 4) if sma200 is not None else None,
        'price_vs_sma50': price_vs_sma50,
        'price_vs_sma200': price_vs_sma200,
        'bb_position': bb_pos,
        'volume_ratio': vol_ratio,
        'in_uptrend': in_uptrend,
        'atr_pct': atr_pct,
        'consecutive_red_candles': consecutive_red,
    }


def fetch_market_context_at(symbol, timestamp_ms, timeframe='4h'):
    """
    Reconstruye el snapshot de indicadores técnicos tal como estaban
    en el momento *histórico* indicado por `timestamp_ms` (Unix ms).

    Esto es esencial para enriquecer transacciones antiguas con el contexto
    correcto del mercado en el momento en que la ballena realmente operó,
    en lugar del momento en que la sincronizamos.

    Args:
        symbol: Símbolo del token (ej: 'SOL', 'WIF')
        timestamp_ms: Timestamp Unix en milisegundos del momento de la tx
        timeframe: Temporalidad de las velas ('1h', '4h', '1d')

    Returns:
        dict con indicadores, igual que fetch_market_context(), o None si falla.
    """
    symbol_upper = symbol.upper().strip()

    if symbol_upper in ('USDC', 'USDT', 'DAI', 'BUSD', 'FDUSD'):
        return None

    pair = f"{symbol_upper}/USDT"
    bar_ms = _TIMEFRAME_MS.get(timeframe, _TIMEFRAME_MS['4h'])

    # Pedir 120 velas que terminen ANTES del timestamp de la tx.
    # La última vela cerrada antes de ese instante es la que la ballena vio.
    limit = 120
    # `since` = inicio de la ventana de 120 velas anterior al timestamp
    since = timestamp_ms - (limit * bar_ms)

    try:
        exchange = _get_binance()
        ohlcv = exchange.fetch_ohlcv(pair, timeframe=timeframe, since=since, limit=limit)

        if not ohlcv or len(ohlcv) < 30:
            return None

        import pandas as pd
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

        # Filtrar solo las velas cuyo CIERRE ya ocurrió antes del timestamp de la tx.
        # Así evitamos usar información futura que la ballena no podía conocer.
        tx_dt = pd.to_datetime(timestamp_ms, unit='ms', utc=True)
        df_hist = df[df['timestamp'] <= tx_dt]

        if len(df_hist) < 30:
            return None

        context = _calculate_indicators(df_hist)
        context['pair'] = pair
        context['timeframe'] = timeframe
        context['candles_used'] = len(df_hist)
        context['reconstructed_at'] = timestamp_ms  # Marca que es dato histórico

        return context

    except ccxt.BadSymbol:
        return None
    except Exception as e:
        print(f"[Whale Intelligence] Error fetching historical context for {symbol} @ {timestamp_ms}: {e}")
        return None
