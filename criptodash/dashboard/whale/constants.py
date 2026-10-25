"""
whale/constants.py — constantes unificadas del módulo Whale Intelligence.

- STABLES: lista única de stablecoins (antes dispersa en 5 archivos).
- EXCHANGE_HOT_WALLETS: hot wallets públicas conocidas de exchanges
  centralizados por blockchain, para detección de flujos ballena↔CEX.

⚠️ Los exchanges rotan sus hot wallets; esta lista debe mantenerse.
Estructura extensible: agregar direcciones a cada exchange sin tocar código.
"""
import logging

logger = logging.getLogger(__name__)

# ================================================================
# STABLECOINS (unificada)
# ================================================================
STABLES = ('USDC', 'USDT', 'DAI', 'PYUSD', 'UST', 'BUSD', 'FDUSD', 'TUSD')

# ================================================================
# HOT WALLETS DE EXCHANGES CENTRALIZADOS (por blockchain, lowercase)
# ================================================================
EXCHANGE_HOT_WALLETS = {
    'ethereum': {
        'Binance': [
            '0x28c6c06298d514db089934071355e5743bf21d60',  # Binance 14
            '0x21a31ee1afc51d94c2efccaa2092ad1028285549',  # Binance 15
            '0xdfd5293d8e347dfe59e90efd55b2956a1343963d',  # Binance 16
        ],
        'Coinbase': [
            '0xa9d1e08c7793af67e9d92fe308d5697fb81d3e43',  # Coinbase 1
        ],
        'Kraken': [
            '0x267be1c1d684f78cb4f6a176c4911b741e4ffdc0',
        ],
        'OKX': [
            '0x6cc5f688a315f3dc28a7781717a9a798a59fda7b',
        ],
        'Bybit': [
            '0x1db92e2eebc8e0c075a02bea49a2935bcd2dfcf4',
        ],
    },
    'bsc': {
        'Binance': [
            '0x8894e0a0c962cb723c1976a4421c95949be2d4e3',  # Binance hot wallet BSC
        ],
    },
    'solana': {
        'Binance': [
            '5tzfkikscxhk5zxcgbxzxdw7gtjjd1mbwuofbhuvuai9',  # Binance Solana hot wallet
        ],
    },
    # 'base': agregar hot wallets conocidas cuando se verifiquen
}

# Índice inverso: address lowercase → (blockchain, exchange)
_HOT_WALLET_INDEX = None


def build_hot_wallet_index():
    """Construye (una vez) el índice inverso address → (blockchain, exchange)."""
    global _HOT_WALLET_INDEX
    if _HOT_WALLET_INDEX is not None:
        return _HOT_WALLET_INDEX
    _HOT_WALLET_INDEX = {}
    for blockchain, exchanges in EXCHANGE_HOT_WALLETS.items():
        for exchange, addresses in exchanges.items():
            for addr in addresses:
                _HOT_WALLET_INDEX[addr.lower()] = (blockchain, exchange)
    return _HOT_WALLET_INDEX


def lookup_exchange_wallet(address: str):
    """
    Devuelve (blockchain, exchange) si la dirección es una hot wallet conocida,
    o None si no lo es.
    """
    if not address:
        return None
    return build_hot_wallet_index().get(address.lower())
