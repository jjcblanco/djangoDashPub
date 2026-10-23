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

    BSC: el plan gratuito de Etherscan V2 NO cubre chainid 56, así que
    BSC usa el endpoint clásico de BscScan (mismos parámetros, sin chainid).
    """
    API_URL = 'https://api.etherscan.io/v2/api'
    CHAIN_IDS = {
        'ethereum': 1,
        'base': 8453,
        'bsc': 56,
    }
    # Endpoints clásicos por cadena (cuando V2 no los cubre en plan gratuito)
    CHAIN_API_URLS = {
        'bsc': 'https://api.bscscan.com/api',
    }

    def __init__(self, blockchain):
        self.blockchain = blockchain
        self.chain_id = self.CHAIN_IDS.get(blockchain, 1)
        self.api_url = self.CHAIN_API_URLS.get(blockchain, self.API_URL)
        # Cargar key de .env usando python-decouple
        from decouple import config
        self.api_key = config(f"{blockchain.upper()}_API_KEY", default="")
        if not self.api_key:
            # Fallback: intentar con ETH_API_KEY
            self.api_key = config('ETH_API_KEY', default="")
        if not self.api_key:
            logger.warning(f"[EVM Tracker] No API key for {blockchain}. API calls will fail.")

    def sync_wallet(self, wallet_obj, max_new=10, **kwargs):
        """Sincroniza transferencias de tokens ERC20 usando Etherscan V2 (o BscScan clásico)."""
        params = {
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
        # La API V2 unificada requiere chainid; los endpoints clásicos no lo usan
        if self.api_url == self.API_URL:
            params['chainid'] = self.chain_id

        headers = {
            'User-Agent': 'WhaleTracker/1.0',
            'Accept': 'application/json'
        }

        try:
            resp = requests.get(self.api_url, params=params, headers=headers, timeout=12)
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
 
class BscRpcWhaleTracker:
    """Rastreador de BNB Chain vía RPC público (eth_getLogs de eventos Transfer ERC-20).

    No requiere API key de BscScan. Si se configura BSC_RPC_URL en el .env
    (p. ej. un endpoint gratuito de Ankr/NodeReal, recomendado) se usa ese;
    si no, los dataseed públicos de Binance con ventanas adaptativas (su
    límite de resultados por query es bajo, así que la ventana se achica
    automáticamente ante 'limit exceeded').
    """
    TRANSFER_TOPIC = '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef'

    RPC_ENDPOINTS = [
        'https://bsc-dataseed.binance.org',
        'https://bsc-dataseed1.defibit.io',
        'https://bsc-dataseed2.binance.org',
        'https://bsc-dataseed3.binance.org',
    ]

    # Símbolos conocidos de BSC para no gastar eth_calls
    KNOWN_TOKENS = {
        '0xbb4cdb9cbd36b01bd1cbaebf2de08d9173bc095c': 'WBNB',
        '0x55d398326f99059ff775485246999027b3197955': 'USDT',
        '0x8ac76a51cc950d9822d68b83fe1ad97b32cd580d': 'USDC',
        '0xe9e7cea3dedca5984780bafc599bd69add087d56': 'BUSD',
        '0x0e09fabb73bd3ade0a17ecc321fd13a19e81ce82': 'CAKE',
    }

    def __init__(self, rpc_url=None):
        from decouple import config
        self.rpc_url = rpc_url or config('BSC_RPC_URL', default='')
        self._endpoint_idx = 0
        self._symbol_cache = {}
        self._decimals_cache = {}

    @property
    def endpoint(self):
        if self.rpc_url:
            return self.rpc_url
        return self.RPC_ENDPOINTS[self._endpoint_idx % len(self.RPC_ENDPOINTS)]

    def _call(self, method, params):
        """Llama al RPC con rotación de endpoints. Retorna (result, err)."""
        payload = {'jsonrpc': '2.0', 'method': method, 'params': params, 'id': 1}
        attempts = len(self.RPC_ENDPOINTS) if not self.rpc_url else 1
        last_err = None
        for _ in range(attempts):
            try:
                r = requests.post(self.endpoint, json=payload, timeout=12)
                data = r.json()
                if 'error' in data:
                    code = data['error'].get('code')
                    if code == -32005:
                        return None, 'limit_exceeded'
                    last_err = data['error'].get('message', 'rpc error')
                else:
                    return data.get('result'), None
            except Exception as e:
                last_err = str(e)
            self._endpoint_idx += 1  # rotar endpoint
        return None, last_err

    def _get_latest_block(self):
        res, _ = self._call('eth_blockNumber', [])
        return int(res, 16) if res else None

    @staticmethod
    def _pad_address(address):
        return '0x' + address.lower().replace('0x', '').zfill(64)

    @staticmethod
    def _decode_abi_string(hex_str):
        """Decodifica el retorno ABI de symbol() (string dinámica)."""
        if not hex_str or hex_str == '0x':
            return None
        data = hex_str[2:] if hex_str.startswith('0x') else hex_str
        if len(data) < 64:
            return None
        offset = int(data[:64], 16) * 2  # offset en bytes → chars hex
        if offset >= len(data):
            return None
        length = int(data[offset:offset + 64], 16)
        raw = data[offset + 64:offset + 64 + length * 2]
        try:
            return bytes.fromhex(raw).decode('utf-8', 'replace')
        except ValueError:
            return None

    def _token_meta(self, contract):
        """Devuelve (symbol, decimals) con caché; eth_call symbol()/decimals()."""
        contract_l = contract.lower()
        if contract_l in self.KNOWN_TOKENS:
            return self.KNOWN_TOKENS[contract_l], 18
        if contract_l in self._symbol_cache:
            return self._symbol_cache[contract_l], self._decimals_cache.get(contract_l, 18)

        symbol = None
        decimals = 18
        # symbol() = 0x95d89b41, decimals() = 0x313ce567
        sym_res, _ = self._call('eth_call', [{'to': contract_l, 'data': '0x95d89b41'}, 'latest'])
        if sym_res:
            symbol = self._decode_abi_string(sym_res)
        dec_res, _ = self._call('eth_call', [{'to': contract_l, 'data': '0x313ce567'}, 'latest'])
        if dec_res:
            try:
                decimals = int(dec_res, 16)
            except (TypeError, ValueError):
                decimals = 18

        symbol = (symbol or '')[:40].strip() or None
        self._symbol_cache[contract_l] = symbol
        self._decimals_cache[contract_l] = decimals
        return symbol, decimals

    def _fetch_transfers(self, address, from_block, to_block, direction):
        """direction 'in' = transferencias hacia la wallet (compras); 'out' = desde (ventas)."""
        topics = [self.TRANSFER_TOPIC]
        if direction == 'out':
            topics += [self._pad_address(address), None]
        else:
            topics += [None, self._pad_address(address)]
        return self._call('eth_getLogs', [{
            'fromBlock': hex(from_block),
            'toBlock': hex(to_block),
            'topics': topics,
        }])

    def sync_wallet(self, wallet_obj, max_new=10, **kwargs):
        """Sincroniza transfers ERC-20 de la wallet en BSC vía RPC."""
        deep_sync = kwargs.get('deep_sync', False)
        latest = self._get_latest_block()
        if not latest:
            logger.error(f"[BSC RPC] No se pudo obtener el último bloque para {wallet_obj.address[:10]}")
            return 0

        new_txs = 0
        to_block = latest
        max_windows = 12 if deep_sync else 6
        window_blocks = 600  # ~30 min de BSC (3s/block)

        # Cache de timestamps de bloques dentro de este sync
        block_ts = {}

        def get_block_timestamp(block_number):
            if block_number not in block_ts:
                res, _ = self._call('eth_getBlockByNumber', [hex(block_number), False])
                ts = res.get('timestamp') if res else None
                block_ts[block_number] = int(ts, 16) if isinstance(ts, str) and ts.startswith('0x') else ts
            return block_ts.get(block_number)

        for _window in range(max_windows):
            if new_txs >= max_new or to_block <= 0:
                break

            win = window_blocks
            processed = False
            while not processed:
                from_block = max(0, to_block - win)
                logs_in, err_in = self._fetch_transfers(wallet_obj.address, from_block, to_block, 'in')
                logs_out, err_out = self._fetch_transfers(wallet_obj.address, from_block, to_block, 'out')

                if err_in == 'limit_exceeded' or err_out == 'limit_exceeded':
                    if win <= 50:
                        logger.warning(f"[BSC RPC] Ventana mínima aún excede límite para {wallet_obj.address[:10]}; salto esta ventana.")
                        processed = True
                    else:
                        win = max(50, win // 2)  # achicar ventana y reintentar
                    continue
                processed = True

                # Procesar en orden: primero ventas (para cerrar trades antes de abrir nuevos)
                for log, direction in [(l, 'out') for l in (logs_out or [])] + [(l, 'in') for l in (logs_in or [])]:
                    if new_txs >= max_new:
                        break
                    tx_hash = log.get('transactionHash', '')
                    if not tx_hash:
                        continue
                    unique_hash = f"bsc_{tx_hash}_{log.get('logIndex', '0')}"
                    if WhaleTransaction.objects.filter(tx_hash=unique_hash).exists():
                        continue

                    contract = log.get('address', '')
                    raw_amount = int(log.get('data', '0x0'), 16) if isinstance(log.get('data'), str) else 0
                    symbol, decimals = self._token_meta(contract)
                    amount = raw_amount / (10 ** decimals) if decimals else float(raw_amount)

                    block_number = int(log.get('blockNumber', '0x0'), 16)
                    block_ts_val = get_block_timestamp(block_number)
                    if block_ts_val:
                        timestamp = timezone.make_aware(datetime.fromtimestamp(block_ts_val))
                    else:
                        timestamp = timezone.now()

                    raw_with_context = dict(log)
                    raw_with_context['contractAddress'] = contract
                    raw_with_context['tokenSymbol'] = symbol or contract[:10] + '...'

                    if symbol:
                        try:
                            from dashboard.whale.context import fetch_market_context
                            mkt_ctx = fetch_market_context(symbol)
                            if mkt_ctx:
                                raw_with_context['market_context'] = mkt_ctx
                        except Exception:
                            pass

                    is_buy = direction == 'in'
                    WhaleTransaction.objects.create(
                        wallet=wallet_obj,
                        tx_hash=unique_hash,
                        timestamp=timestamp,
                        tx_type='BUY' if is_buy else 'SELL',
                        from_asset=None if is_buy else (symbol or contract[:10] + '...'),
                        to_asset=(symbol or contract[:10] + '...') if is_buy else None,
                        amount_in=amount,
                        raw_data=raw_with_context,
                    )
                    new_txs += 1

            to_block = from_block - 1

        return new_txs


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
