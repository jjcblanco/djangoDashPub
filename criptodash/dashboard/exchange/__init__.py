"""
dashboard/exchange — cliente exchange unificado (Fase 2b).

Uso recomendado:
    from dashboard.exchange import get_binance, get_public_binance, fetch_ohlcv_paginated
"""
from .client import get_binance, get_public_binance, fetch_ohlcv_paginated

__all__ = ['get_binance', 'get_public_binance', 'fetch_ohlcv_paginated']
