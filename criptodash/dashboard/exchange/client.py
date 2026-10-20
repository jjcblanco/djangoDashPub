"""
dashboard/exchange/client.py
============================
Cliente exchange unificado (Fase 2b).

Reemplaza los múltiples clientes ccxt que existían dispersos por el repo:
- ccxttest1.py (singleton sin enableRateLimit)
- pair_scanner._get_exchange() (instancia nueva por llamada)
- whale/context.py _get_binance() (público sin key)
- utils/performance.py (instancia privada con key)

Un solo cliente, con enableRateLimit, configurado en un solo lugar.
Los módulos viejos quedan como shims que delegan acá (ver plan Fase 2b).
"""
import logging
import threading

import ccxt
from django.conf import settings

logger = logging.getLogger(__name__)

# Singletons
_binance = None
_public_binance = None
_lock = threading.Lock()


def get_binance():
    """
    Instancia única de ccxt.binance con API keys (para operar).
    enableRateLimit=True evita baneos de Binance por ráfagas.
    """
    global _binance
    with _lock:
        if _binance is None:
            _binance = ccxt.binance({
                'apiKey': getattr(settings, 'BINANCE_APIKEY', None),
                'secret': getattr(settings, 'BINANCE_SECRET', None),
                'enableRateLimit': True,
                'timeout': 10000,  # 10 segundos
                'options': {
                    'recvWindow': 60000,
                    'adjustForTimeDifference': True,
                    'defaultType': 'spot',
                },
            })
            logger.info("Cliente Binance unificado creado (con API keys).")
        return _binance


def get_public_binance():
    """
    Instancia única de ccxt.binance SIN API keys (solo datos públicos).
    """
    global _public_binance
    with _lock:
        if _public_binance is None:
            _public_binance = ccxt.binance({
                'enableRateLimit': True,
                'timeout': 10000,
                'options': {
                    'adjustForTimeDifference': True,
                    'defaultType': 'spot',
                },
            })
            logger.info("Cliente Binance público creado (sin API keys).")
        return _public_binance


def fetch_ohlcv_paginated(symbol, timeframe='1h', since=None, limit=None):
    """
    Descarga OHLCV con paginación (lógica migrada de
    ccxttest1.historical_fetch_ohlcv, ahora sobre el cliente unificado).
    """
    exchange = get_binance()
    exchange.load_markets()

    if since is None:
        # Por defecto los últimos 1000 bars
        return exchange.fetch_ohlcv(symbol, timeframe, limit=1000)

    # Manejar datetime objects
    if hasattr(since, 'strftime'):
        from_ts = int(since.timestamp() * 1000)
    else:
        # Asumir string para parse8601
        try:
            parsed = exchange.parse8601(str(since))
            from_ts = int(parsed) if parsed is not None else None
        except Exception:
            # Si ya es un timestamp
            from_ts = int(float(since))

    ohlcv_list = []
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe, since=from_ts, limit=1000)
    if not ohlcv:
        return []

    ohlcv_list.extend(ohlcv)

    # Si pedimos un límite específico y ya lo tenemos, paramos
    if limit and len(ohlcv_list) >= limit:
        return ohlcv_list[:limit]

    while True:
        from_ts = ohlcv_list[-1][0] + 1  # +1 para no repetir la última vela
        new_ohlcv = exchange.fetch_ohlcv(symbol, timeframe, since=from_ts, limit=1000)
        if not new_ohlcv:
            break
        ohlcv_list.extend(new_ohlcv)
        if len(new_ohlcv) != 1000:
            break
        if limit and len(ohlcv_list) >= limit:
            return ohlcv_list[:limit]

    return ohlcv_list
