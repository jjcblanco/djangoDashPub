import requests
import time
import logging
from datetime import datetime
from django.utils import timezone
from ..models import WhaleTransaction

logger = logging.getLogger(__name__)

class SolanaWhaleTracker:
    def __init__(self, rpc_url=None):
        self.rpc_url = rpc_url or "https://api.mainnet-beta.solana.com"

    def get_transactions(self, address, limit=None):
        if limit is None:
            limit = 50 
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getSignaturesForAddress",
            "params": [address, {"limit": limit}]
        }
        try:
            response = requests.post(self.rpc_url, json=payload, timeout=10)
            return response.json().get('result', [])
        except:
            return []

    def get_transaction_details(self, tx_hash):
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getTransaction",
            "params": [tx_hash, {"encoding": "json", "maxSupportedTransactionVersion": 0}]
        }
        try:
            response = requests.post(self.rpc_url, json=payload, timeout=10)
            return response.json().get('result', {})
        except:
            return {}

    def sync_wallet(self, wallet_obj, max_new=5, signatures_limit=None):
        signatures = self.get_transactions(wallet_obj.address, limit=signatures_limit)
        new_txs = 0
        for sig in signatures:
            if new_txs >= max_new: break
            tx_hash = sig['signature']
            if WhaleTransaction.objects.filter(tx_hash=tx_hash).exists(): continue
            details = self.get_transaction_details(tx_hash)
            if not details: continue
            timestamp = timezone.make_aware(datetime.fromtimestamp(sig['blockTime'])) if sig.get('blockTime') else timezone.now()
            WhaleTransaction.objects.create(
                wallet=wallet_obj, tx_hash=tx_hash, timestamp=timestamp,
                tx_type="UNKNOWN", raw_data=details
            )
            new_txs += 1
        return new_txs

class EVMWhaleTracker:
    """Rastreador para redes EVM (Ethereum, Base, etc) usando Etherscan V2 API unificada.
    
    Etherscan V2 usa un endpoint único para todas las cadenas,
    diferenciándolas por el parámetro chainid.
    Plan gratuito: 5 calls/sec.
    """
    API_URL = 'https://api.etherscan.io/v2/api'
    CHAIN_IDS = {
        'ethereum': 1,
        'base': 8453,
    }

    def __init__(self, blockchain):
        self.blockchain = blockchain
        self.chain_id = self.CHAIN_IDS.get(blockchain, 1)
        # Cargar key de .env usando python-decouple
        from decouple import config
        self.api_key = config(f"{blockchain.upper()}_API_KEY", default="")
        if not self.api_key:
            # Fallback: intentar con ETH_API_KEY
            self.api_key = config('ETH_API_KEY', default="")
        if not self.api_key:
            logger.warning(f"[EVM Tracker] No API key for {blockchain}. API calls will fail.")

    def sync_wallet(self, wallet_obj, max_new=10, **kwargs):
        """Sincroniza transferencias de tokens ERC20 usando Etherscan V2."""
        params = {
            'chainid': self.chain_id,
            'module': 'account',
            'action': 'tokentx',
            'address': wallet_obj.address,
            'startblock': 0,
            'endblock': 99999999,
            'page': 1,
            'offset': 50,
            'sort': 'desc',
            'apikey': self.api_key
        }
        
        headers = {
            'User-Agent': 'WhaleTracker/1.0',
            'Accept': 'application/json'
        }
        
        try:
            resp = requests.get(self.API_URL, params=params, headers=headers, timeout=12)
            if resp.status_code != 200:
                logger.error(f"[EVM Tracker] HTTP {resp.status_code} for {wallet_obj.address[:10]} ({self.blockchain})")
                return 0
            
            data = resp.json()
            if data.get('status') != '1':
                error_msg = data.get('message', 'Unknown V2 API error')
                result_msg = data.get('result', 'No result')
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"[EVM Tracker V2] API error for {wallet_obj.address[:10]}: {error_msg} - Result: {result_msg}")
                
                # Special handling for common V2 errors
                if 'rate limit' in error_msg.lower():
                    logger.warning(f"[EVM Tracker V2] Rate limit hit for {self.blockchain}")
                elif 'invalid api key' in error_msg.lower():
                    logger.error(f"[EVM Tracker V2] Invalid API key for {self.blockchain}")
                
                return 0
            
            transfers = data.get('result', [])
            new_txs = 0
            
            for tx in transfers:
                if new_txs >= max_new:
                    break
                
                # Usamos blockNumber + hash para unicidad si hay múltiples transferencias en un hash
                unique_hash = f"{tx['hash']}_{tx.get('logIndex', '0')}"
                if WhaleTransaction.objects.filter(tx_hash=unique_hash).exists():
                    continue
                
                # Parsear timestamp de EVM (está en format string o int según API)
                ts_val = int(tx.get('timeStamp', time.time()))
                timestamp = timezone.make_aware(datetime.fromtimestamp(ts_val))
                
                raw_with_context = dict(tx)
                
                # Capturar contexto de mercado (indicadores técnicos)
                try:
                    from dashboard.whale.context import fetch_market_context
                    token_symbol = tx.get('tokenSymbol')
                    if token_symbol:
                        mkt_ctx = fetch_market_context(token_symbol)
                        if mkt_ctx:
                            raw_with_context['market_context'] = mkt_ctx
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f"[EVM] No se pudo capturar contexto de mercado para {tx.get('tokenSymbol')}: {e}")
                
                WhaleTransaction.objects.create(
                    wallet=wallet_obj,
                    tx_hash=unique_hash,
                    timestamp=timestamp,
                    tx_type="BUY" if tx.get('to', '').lower() == wallet_obj.address.lower() else "SELL",
                    from_asset=None if tx.get('to', '').lower() == wallet_obj.address.lower() else tx.get('tokenSymbol'),
                    to_asset=tx.get('tokenSymbol') if tx.get('to', '').lower() == wallet_obj.address.lower() else None,
                    amount_in=float(tx.get('value', 0)) / (10 ** int(tx.get('tokenDecimal', 18))),
                    raw_data=raw_with_context
                )
                new_txs += 1
            return new_txs
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"[EVM Tracker] Error sincronizando wallet {wallet_obj.address[:10]}: {e}")
            return 0
 
class HyperliquidWhaleTracker:
    """Rastreador para la red Hyperliquid L1 usando su API de Info."""
    API_URL = "https://api.hyperliquid.xyz/info"

    def sync_wallet(self, wallet_obj, max_new=20, **kwargs):
        """Sincroniza los últimos trades (fills) del usuario."""
        payload = {
            "type": "userFills",
            "user": wallet_obj.address
        }
        try:
            resp = requests.post(self.API_URL, json=payload, timeout=15)
            if resp.status_code != 200: return 0
            
            fills = resp.json()
            if not isinstance(fills, list): return 0
            
            # HL 'time' es el timestamp en ms.
            fills.sort(key=lambda x: x['time'], reverse=True)
            
            new_txs = 0
            for fill in fills:
                if new_txs >= max_new: break
                
                # Unicidad basada en hash de la transacción o ID del fill
                unique_hash = f"hl_{fill.get('tid', fill['time'])}"
                if WhaleTransaction.objects.filter(tx_hash=unique_hash).exists():
                    continue
                
                timestamp = timezone.make_aware(datetime.fromtimestamp(fill['time'] / 1000.0))
                
                # En HL, un fill es un trade (compra o venta)
                raw_with_context = dict(fill)
                
                # Capturar contexto de mercado (indicadores técnicos)
                try:
                    from dashboard.whale.context import fetch_market_context
                    coin = fill.get('coin')
                    if coin:
                        mkt_ctx = fetch_market_context(coin)
                        if mkt_ctx:
                            raw_with_context['market_context'] = mkt_ctx
                except Exception:
                    pass  # No bloquear sync si falla el contexto
                
                WhaleTransaction.objects.create(
                    wallet=wallet_obj,
                    tx_hash=unique_hash,
                    timestamp=timestamp,
                    tx_type="SWAP",
                    from_asset="USDC",
                    to_asset=fill.get('coin'),
                    amount_in=float(fill.get('sz', 0)) * float(fill.get('px', 0)),
                    amount_out=float(fill.get('sz', 0)),
                    raw_data=raw_with_context
                )
                new_txs += 1
            return new_txs
        except Exception as e:
            logger.error(f"[Hyperliquid Tracker] Error sincronizando wallet {wallet_obj.address[:10]}: {e}")
            return 0
