import requests
import time

# ──────────────────────────────────────────────────────────────
# Re-exportaciones del paquete dashboard.whale
# (retrocompatibilidad con imports tipo `from dashboard.services import PatternEngine`)
# ──────────────────────────────────────────────────────────────
from .whale.trackers import SolanaWhaleTracker, EVMWhaleTracker, HyperliquidWhaleTracker
from .whale.pipeline import PatternEngine, get_whale_score, get_top_scored_whales, update_all_whale_scores

# ============================================================
# Utilidad de Precios en Tiempo Real
# ============================================================

# Mapeo de símbolos comunes a IDs de CoinGecko
COINGECKO_ID_MAP = {
    'SOL': 'solana',
    'ETH': 'ethereum',
    'BTC': 'bitcoin',
    'BNB': 'binancecoin',
    'AVAX': 'avalanche-2',
    'MATIC': 'matic-network',
    'ARB': 'arbitrum',
    'OP': 'optimism',
    'DOGE': 'dogecoin',
    'SHIB': 'shiba-inu',
    'PEPE': 'pepe',
    'WIF': 'dogwifcoin',
    'JUP': 'jupiter-exchange-solana',
    'BONK': 'bonk',
    'LINK': 'chainlink',
    'UNI': 'uniswap',
    'AAVE': 'aave',
    'RENDER': 'render-token',
    'FET': 'fetch-ai',
    'INJ': 'injective-protocol',
    'SUI': 'sui',
    'APT': 'aptos',
    'SEI': 'sei-network',
    'TIA': 'celestia',
    'PYTH': 'pyth-network',
    'W': 'wormhole',
    'JTO': 'jito-governance-token',
    'HYPE': 'hyperliquid',
    'PURR': 'purr-2',
}

# Cache de precios para evitar saturar APIs en bucles
_PRICE_CACHE = {}

def fetch_current_price(symbol):
    """
    Obtiene el precio actual en USD de un token usando CoinGecko o cache.
    Retorna float o None si no se puede obtener.
    """
    import time # Added import for time.time()
    import requests # Added import for requests.get()

    if not symbol: return None
    symbol_upper = symbol.upper().strip()
    
    # 1. Verificar Cache (TTL 60s)
    now = time.time()
    if symbol_upper in _PRICE_CACHE:
        ts, cached_price = _PRICE_CACHE[symbol_upper]
        if now - ts < 60:
            return cached_price
            
    # Stablecoins → siempre $1
    if symbol_upper in ('USDC', 'USDT', 'DAI', 'BUSD', 'TUSD', 'FDUSD'):
        return 1.0
    
    coin_id = COINGECKO_ID_MAP.get(symbol_upper)
    if not coin_id:
        # Intentar buscar directamente por símbolo en minúsculas
        coin_id = symbol_upper.lower()
    
    try:
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd"
        resp = requests.get(url, timeout=5) # Reducido timeout de 10 a 5
        if resp.status_code == 200:
            data = resp.json()
            if coin_id in data and 'usd' in data[coin_id]:
                price = float(data[coin_id]['usd'])
                _PRICE_CACHE[symbol_upper] = (now, price)
                return price
    except Exception as e:
        print(f"[Price Fetch Error] {symbol}: {e}")
    
