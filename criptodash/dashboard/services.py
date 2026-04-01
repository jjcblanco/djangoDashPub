import requests
import os
import json
import time
import logging
from datetime import datetime
from django.utils import timezone
from .models import WhaleWallet, WhaleTransaction, PatternInsight, ShadowTrade
from .utils.notifications import send_telegram_message

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
    """Rastreador para redes EVM (Ethereum, Base, etc) usando APIs compatibles con Etherscan."""
    API_CONFIG = {
        'ethereum': 'https://api.etherscan.io/api',
        'base': 'https://api.basescan.org/api',
    }

    def __init__(self, blockchain):
        self.blockchain = blockchain
        self.api_url = self.API_CONFIG.get(blockchain, self.API_CONFIG['ethereum'])
        # Podríamos cargar keys de .env aquí si existen
        self.api_key = os.environ.get(f"{blockchain.upper()}_API_KEY", "")

    def sync_wallet(self, wallet_obj, max_new=10, **kwargs):
        """Sincroniza transferencias de tokens ERC20."""
        # limit=50 para background, menos para web (ignorado si max_new es bajo)
        params = {
            'module': 'account',
            'action': 'tokentx',
            'address': wallet_obj.address,
            'sort': 'desc',
            'page': 1,
            'offset': 50,
            'apikey': self.api_key
        }
        try:
            resp = requests.get(self.api_url, params=params, timeout=12)
            if resp.status_code != 200: return 0
            
            data = resp.json()
            if data.get('status') != '1': return 0
            
            transfers = data.get('result', [])
            new_txs = 0
            
            for tx in transfers:
                if new_txs >= max_new: break
                
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
                    from dashboard.whale_intelligence import fetch_market_context
                    token_symbol = tx.get('tokenSymbol')
                    if token_symbol:
                        mkt_ctx = fetch_market_context(token_symbol)
                        if mkt_ctx:
                            raw_with_context['market_context'] = mkt_ctx
                except Exception as e:
                    logger.warning(f"[EVM] No se pudo capturar contexto de mercado para {tx.get('tokenSymbol')}: {e}")
                
                WhaleTransaction.objects.create(
                    wallet=wallet_obj,
                    tx_hash=unique_hash,
                    timestamp=timestamp,
                    tx_type="SWAP" if tx.get('to').lower() == wallet_obj.address.lower() else "TRANSFER",
                    from_asset=tx.get('tokenSymbol'), # No lo sabemos aún con certeza, pero tokentx nos da el asset que se movió
                    to_asset=tx.get('tokenSymbol'),
                    amount_in=float(tx.get('value', 0)) / (10 ** int(tx.get('tokenDecimal', 18))),
                    raw_data=raw_with_context
                )
                new_txs += 1
            return new_txs
        except Exception as e:
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
                    from dashboard.whale_intelligence import fetch_market_context
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

class PatternEngine:
    _TOKEN_SYMBOL_CACHE = {}

    @staticmethod
    def get_token_symbol(mint):
        """Busca el símbolo de un token dinámicamente usando la API de Jupiter."""
        # 1. Caché estática básica (Tokens comunes)
        TOKEN_MAP = {
            'So11111111111111111111111111111111111111112': 'SOL',
            'EPjFW3F2KVq2aLecqCP5i5nw53J2tOt9iies23XYwjLu': 'USDC',
            'Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB': 'USDT',
            'JUPyiPZp718zay7kaPn2CoJvRwvpqcRuS5B7shuYf79': 'JUP',
            'DezXAZ8z7Pnrn9vzctrxEXpWMrNHqR1f6f69nL4XYUDx': 'BONK',
        }
        
        if mint in TOKEN_MAP:
            return TOKEN_MAP[mint]
            
        # 2. Verificar caché en memoria
        if mint in PatternEngine._TOKEN_SYMBOL_CACHE:
            return PatternEngine._TOKEN_SYMBOL_CACHE[mint]
            
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        try:
            # Opción 1: Jupiter API
            url = f"https://tokens.jup.ag/token/{mint}"
            resp = requests.get(url, headers=headers, timeout=3)
            if resp.status_code == 200:
                data = resp.json()
                if data.get('symbol'):
                    symbol = data['symbol']
                    PatternEngine._TOKEN_SYMBOL_CACHE[mint] = symbol
                    return symbol
            
            # Opción 2: DexScreener API
            url_dex = f"https://api.dexscreener.com/latest/dex/tokens/{mint}"
            resp_dex = requests.get(url_dex, headers=headers, timeout=3)
            if resp_dex.status_code == 200:
                data_dex = resp_dex.json()
                pairs = data_dex.get('pairs', [])
                if pairs:
                    symbol = pairs[0].get('baseToken', {}).get('symbol', mint[:8] + "...")
                    PatternEngine._TOKEN_SYMBOL_CACHE[mint] = symbol
                    return symbol
        except Exception as e:
            try:
                with open('whale_debug.log', 'a') as f:
                    f.write(f"Error resolviendo token {mint}: {e}\n")
            except: pass
        
        return mint[:8] + "..."

    @staticmethod
    def get_wallet_pnl(wallet_obj):
        """Calcula el P&L aproximado de los últimos movimientos."""
        txs = wallet_obj.transactions.order_by('-timestamp')[:100]
        if not txs.exists():
            return {'roi': 0, 'pnl_usdt': 0, 'status': 'neutral'}
            
        # Simplificación: Seguimiento de SOL como base de "coste" si es Solana
        # En una versión avanzada, rastrearíamos cada token contra USDC
        pnl_data = {'roi': 0, 'pnl_usdt': 0, 'status': 'neutral'}
        
        # Simulación de cálculo basado en balances (Placeholder para lógica compleja)
        # Por ahora devolvemos un aleatorio basado en la confianza para la demo visual
        # y preparamos la estructura para el cálculo real.
        insights = wallet_obj.insights.all()
        if not insights.exists():
            return pnl_data
            
        conf = sum([i.confidence for i in insights]) / insights.count()
        if conf > 0.8:
            pnl_data = {'roi': round(conf * 15, 2), 'pnl_usdt': round(conf * 1200, 2), 'status': 'profit'}
        elif conf > 0.5:
            pnl_data = {'roi': round(conf * 5, 2), 'pnl_usdt': round(conf * 300, 2), 'status': 'profit'}
        else:
            pnl_data = {'roi': round((conf - 0.5) * 10, 2), 'pnl_usdt': round((conf - 0.5) * 500, 2), 'status': 'loss'}
            
        return pnl_data

    @staticmethod
    def analyze_wallet(wallet_obj):
        """Analiza las últimas N transacciones de una billetera para detectar patrones y tokens.
        
        Se limita a las últimas 50 txs para evitar que wallets con miles de transacciones
        colapsen la RAM del worker de Celery. Aumentar el límite con precaución.
        """
        MAX_TXS = 50
        txs = list(wallet_obj.transactions.order_by('-timestamp')[:MAX_TXS])
        if len(txs) < 2:
            return "Datos insuficientes (necesita al menos 2 transacciones)"
            
        token_stats = {} # {token_mint: {'buys': 0, 'volume': 0}}
        
        # Mapeo básico de tokens comunes
        TOKEN_MAP = {
            'So11111111111111111111111111111111111111112': 'SOL',
            'EPjFW3F2KVq2aLecqCP5i5nw53J2tOt9iies23XYwjLu': 'USDC',
            'Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB': 'USDT',
            'JUPyiPZp718zay7kaPn2CoJvRwvpqcRuS5B7shuYf79': 'JUP',
            'DezXAZ8z7Pnrn9vzctrxEXpWMrNHqR1f6f69nL4XYUDx': 'BONK',
        }
        
        # MODIFICACIÓN: Soporte Multi-Red en Análisis
        ESTABLISHED_TOKENS = {
            # Solana
            'So11111111111111111111111111111111111111112': 'SOL',
            'EPjFW3F2KVq2aLecqCP5i5nw53J2tOt9iies23XYwjLu': 'USDC',
            'Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB': 'USDT',
            # Ethereum / Base
            '0xdAC17F958D2ee523a2206206994597C13D831ec7': 'USDT',
            '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48': 'USDC',
            '0x4200000000000000000000000000000000000006': 'WETH',
            '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913': 'USDC',
        }

        for tx in txs:
            try:
                if wallet_obj.blockchain == 'solana':
                    raw = tx.raw_data
                    if not raw or 'meta' not in raw: c                    # Mapeo de balances para el dueño de la billetera
                    pre_balances = {b['mint']: b['uiTokenAmount']['uiAmount'] or 0 
                                   for b in raw['meta'].get('preTokenBalances', []) 
                                   if b.get('owner') == wallet_obj.address}
                    
                    post_balances = {b['mint']: b['uiTokenAmount']['uiAmount'] or 0 
                                    for b in raw['meta'].get('postTokenBalances', []) 
                                    if b.get('owner') == wallet_obj.address}
                    
                    # Detectar cambios en tokens (BUY / SELL)
                    all_mints = set(pre_balances.keys()) | set(post_balances.keys())
                    for mint in all_mints:
                        pre_val = pre_balances.get(mint, 0)
                        post_val = post_balances.get(mint, 0)
                        change = post_val - pre_val
                        
                        if abs(change) > 0:
                            # Filtrado STRICT Dinamico o Estático
                            if wallet_obj.filter_mode == 'STRICT':
                                if mint not in ESTABLISHED_TOKENS:
                                    if not PatternEngine.is_token_reputable(None, mint, 'solana'):
                                        continue
                                
                            token_symbol = PatternEngine.get_token_symbol(mint)
                            
                            # Actualizar TRX
                            if tx.tx_type == "UNKNOWN":
                                tx.tx_type = "BUY" if change > 0 else "SELL"
                                if change > 0:
                                    tx.to_asset = token_symbol
                                    tx.amount_out = change
                                else:
                                    tx.from_asset = token_symbol
                                    tx.amount_in = abs(change)
                                tx.save()
                                        
                            if mint not in token_stats:
                                token_stats[mint] = {'buys': 0, 'sells': 0, 'volume': 0}
                            
                            if change > 0:
                                token_stats[mint]['buys'] += 1
                                token_stats[mint]['volume'] += change
                                PatternEngine._automated_shadow_trade(wallet_obj, token_symbol, tx)
                            else:
                                token_stats[mint]['sells'] += 1
                                # Al vender, cerrar el shadow trade abierto para esta ballena+token
                                PatternEngine._close_shadow_trade(wallet_obj, token_symbol, tx)

                    # Detectar cambios en SOL (Base)
                    try:
                        # Index 0 suele ser el fee payer (ballena)
                        pre_sol = raw['meta'].get('preBalances', [0])[0] / 1e9
                        post_sol = raw['meta'].get('postBalances', [0])[0] / 1e9
                        sol_change = post_sol - pre_sol
                        if abs(sol_change) > 0.001: # Ignorar solo el fee pequeño
                            if tx.tx_type == "UNKNOWN":
                                tx.tx_type = "SWAP" # Si solo se movio SOL
                                tx.save()
                    except Exception:
                        pass  # Cambios en SOL base pueden fallar en txs no estándar

                elif wallet_obj.blockchain == 'hyperliquid':
                    raw = tx.raw_data
                    coin = raw.get('coin')
                    if coin and raw.get('side') == 'B':
                        if coin not in token_stats:
                            token_stats[coin] = {'buys': 0, 'volume': 0, 'symbol': coin}
                        token_stats[coin]['buys'] += 1
                        token_stats[coin]['volume'] += float(raw.get('sz', 0))
                        PatternEngine._automated_shadow_trade(wallet_obj, coin, tx)

                else: # EVM
                    raw = tx.raw_data
                    mint = raw.get('contractAddress')
                    if mint:
                        change = tx.amount_in or 0
                        if change > 0 and tx.tx_type == 'SWAP':
                            symbol = raw.get('tokenSymbol')
                            if wallet_obj.filter_mode == 'STRICT':
                                if mint not in ESTABLISHED_TOKENS:
                                    if not PatternEngine.is_token_reputable(symbol, mint, wallet_obj.blockchain):
                                        continue
                            
                            if mint not in token_stats:
                                token_stats[mint] = {'buys': 0, 'volume': 0, 'symbol': symbol}
                            token_stats[mint]['buys'] += 1
                            token_stats[mint]['volume'] += float(change)
                            PatternEngine._automated_shadow_trade(wallet_obj, symbol, tx)
            except Exception as e:
                logger.warning(f"[analyze_wallet] Error procesando tx {tx.tx_hash[:16]} de {wallet_obj.address[:8]}: {e}")
                continue

        # --- Guardar Top Tokens ---
        if token_stats:
            # Ordenar por número de compras descendente
            sorted_tokens = sorted(
                token_stats.items(), 
                key=lambda x: x[1].get('buys', 0), 
                reverse=True
            )
            top_3 = {}
            for mint, stats in sorted_tokens[:3]:
                symbol = PatternEngine.get_token_symbol(mint) if wallet_obj.blockchain == 'solana' else stats.get('symbol', '???')
                top_3[symbol] = stats.get('buys', 0)
            
            wallet_obj.top_tokens = top_3
            wallet_obj.save()

        return f"Análisis completado para {wallet_obj.address[:8]}"

    @staticmethod
    def discover_token_whales(contract_address, blockchain='ethereum'):
        """
        Escanea el historial de trades de un token usando la API de GeckoTerminal.
        Estrategia 'Gecko-Hunter': Muy superior para encontrar ballenas activas en DEXs.
        """
        # 1. Buscar el Par en DexScreener para obtener el pool_address y network
        pair_data = None
        try:
            dex_url = f"https://api.dexscreener.com/latest/dex/search?q={contract_address}"
            dex_resp = requests.get(dex_url, timeout=8)
            if dex_resp.status_code == 200:
                pairs = dex_resp.json().get('pairs', [])
                if pairs:
                     # Filtrar por blockchain correcta
                     network_map = {'ethereum': 'eth', 'base': 'base', 'solana': 'solana'}
                     target_net = network_map.get(blockchain, 'eth')
                     
                     for p in pairs:
                         if p.get('chainId') == target_net or p.get('chainId') == blockchain:
                             pair_data = p
                             break
        except Exception as e:
            logger.error(f"[Whale Scout] Error buscando par: {e}")

        if not pair_data:
            return []

        pool_address = pair_data.get('pairAddress')
        network = pair_data.get('chainId', 'eth')
        # GeckoTerminal usa 'eth' para ethereum
        if network == 'ethereum': network = 'eth'

        # 2. Consultar GeckoTerminal para los últimos trades del Pool
        # Retorna hasta 300 trades recientes sin necesidad de API Key
        gecko_url = f"https://api.geckoterminal.com/api/v2/networks/{network}/pools/{pool_address}/trades"
        
        try:
            resp = requests.get(gecko_url, timeout=10)
            if resp.status_code != 200: return []
            
            data = resp.json()
            trades = data.get('data', [])
            buyers = {} # {address: {'volume': 0, 'tx_count': 0}}
            
            token_symbol = pair_data.get('baseToken', {}).get('symbol', 'TOKEN')
            
            for t in trades:
                attr = t.get('attributes', {})
                # Solo nos interesan las COMPRAS para encontrar "Ballenas de entrada"
                if attr.get('kind') == 'buy':
                    buyer_addr = attr.get('tx_from_address', '').lower()
                    if not buyer_addr: continue
                    
                    # Usamos el volumen en USD que es más fácil de comparar entre tokens
                    vol_usd = float(attr.get('volume_usd') or 0)
                    # Si vol_usd es 0 (no indexado), intentar usar cantidad de tokens si estuviera disponible
                    # GeckoTerminal no siempre da el amount de tokens en el /trades simplificado
                    
                    if buyer_addr not in buyers:
                        buyers[buyer_addr] = {
                            'volume': 0, 
                            'tx_count': 0, 
                            'symbol': token_symbol, 
                            'address': buyer_addr,
                            'is_usd': True
                        }
                    
                    buyers[buyer_addr]['volume'] += vol_usd
                    buyers[buyer_addr]['tx_count'] += 1
            
            # Ordenar por volumen USD descendente
            sorted_buyers = sorted(buyers.values(), key=lambda x: x['volume'], reverse=True)
            
            # Si no hay vol_usd (muchos aparecen como 0), ordenar por tx_count
            if not sorted_buyers or sorted_buyers[0]['volume'] == 0:
                sorted_buyers = sorted(buyers.values(), key=lambda x: x['tx_count'], reverse=True)
                
            return sorted_buyers[:12]
            
        except Exception as e:
            logger.error(f"[Whale Scout] Error en GeckoTerminal para {pool_address}: {e}")
            return []
                
    @staticmethod
    def _close_shadow_trade(wallet, symbol, tx):
        """Busca un trade abierto para este token y lo cierra calculando PnL."""
        trade = ShadowTrade.objects.filter(
            wallet=wallet,
            token_symbol=symbol,
            status='OPEN'
        ).order_by('-created_at').first()
        
        if not trade: return
        
        # Obtener precio de salida (exit)
        exit_price = 0
        try:
            if 'priceUsd' in tx.raw_data:
                exit_price = float(tx.raw_data['priceUsd'])
            elif 'px' in tx.raw_data:
                exit_price = float(tx.raw_data['px'])
            else:
                from .services import fetch_current_price
                price = fetch_current_price(symbol)
                exit_price = float(price) if price else trade.entry_price
        except: exit_price = trade.entry_price
        
        trade.exit_price = exit_price
        trade.status = 'CLOSED'
        trade.closed_at = tx.timestamp
        
        if float(trade.entry_price) > 0:
            trade.pnl_percent = round(((float(exit_price) - float(trade.entry_price)) / float(trade.entry_price)) * 100, 2)
        
        trade.save()
        PatternEngine._update_whale_dna(wallet)

    @staticmethod
    def _update_whale_dna(wallet):
        """Agrega estadísticas de trades cerrados al perfil DNA de la ballena."""
        trades = ShadowTrade.objects.filter(wallet=wallet, status='CLOSED').order_by('-closed_at')[:20]
        if not trades: return
        
        dna = wallet.trading_dna or {}
        wins = [t for t in trades if t.pnl_percent > 0]
        dna['win_rate'] = round((len(wins) / len(trades)) * 100, 1) if trades else 0
        dna['avg_pnl'] = round(sum([t.pnl_percent for t in trades]) / len(trades), 2) if trades else 0
        
        hold_times = []
        for t in trades:
            if t.closed_at and t.created_at:
                diff = (t.closed_at - t.created_at).total_seconds() / 3600
                if diff > 0: hold_times.append(diff)
        
        if hold_times:
            dna['avg_hold_hours'] = round(sum(hold_times) / len(hold_times), 1)
        
        if dna.get('avg_hold_hours', 0) < 1: dna['style'] = "Sniper"
        elif dna.get('avg_hold_hours', 0) < 24: dna['style'] = "Day Trader"
        else: dna['style'] = "Swing Trader"
            
        rsi_entries = [t.market_context['rsi_14'] for t in trades if t.market_context and 'rsi_14' in t.market_context and t.market_context['rsi_14']]
        if rsi_entries:
            dna['preferred_rsi'] = f"{round(min(rsi_entries))}-{round(max(rsi_entries))}"

        wallet.trading_dna = dna
        wallet.save()
                
        # ... resto del método analyze_wallet ...
        # (Añadir al final de la clase)

    @staticmethod
    def verify_token_security(symbol, tx_raw_data=None):
        """
        Verifica si el token es 'seguro' basándose en liquidez y FDV.
        """
        # Stablecoins son seguros por definición en este contexto
        STABLES = ['USDC', 'USDT', 'DAI', 'PYUSD', 'UST']
        if not symbol or symbol.upper() in STABLES: return True
        
        try:
            # Filtros básicos: Liquidez > $30k, FDV > $100k
            liquidity = float(tx_raw_data.get('liquidity', 0)) if tx_raw_data else 0
            fdv = float(tx_raw_data.get('fdv', 0)) if tx_raw_data else 0
            
            if liquidity > 0 and liquidity < 30000: return False
            if fdv > 0 and fdv < 100000: return False
            
            return True
        except:
            return True

    @staticmethod
    def _check_cohort_consensus(symbol, exclude_wallet_id):
        """
        Verifica cuántas ballenas distintas han comprado este token en las últimas 12 horas.
        """
        from datetime import timedelta
        since = timezone.now() - timedelta(hours=12)
        
        cohort_count = WhaleTransaction.objects.filter(
            to_asset=symbol,
            timestamp__gte=since,
            tx_type__in=['BUY', 'SWAP']
        ).exclude(wallet_id=exclude_wallet_id).values('wallet').distinct().count()
        
        return cohort_count

    @staticmethod
    def _automated_shadow_trade(wallet, symbol, tx):
        """Crea una simulación automática si no existe una reciente para este par."""
        from django.db.models import Q
        from datetime import timedelta
        from .whale_analysis import WhaleAnalysisEngine
        
        # 1. Ignorar Stablecoins conocidos
        STABLES = ['USDC', 'USDT', 'DAI', 'PYUSD', 'UST']
        if not symbol or symbol.upper() in STABLES: return
        
        # 2. Verificar Seguridad del Token
        if not PatternEngine.verify_token_security(symbol, tx.raw_data):
            logger.info(f"Token {symbol} descartado por baja seguridad/liquidez.")
            return

        # 3. Evitar duplicados
        exists = ShadowTrade.objects.filter(
            wallet=wallet,
            token_symbol=symbol,
            status='OPEN'
        ).exists()
        
        if exists: return
        
        # 3. Determinar precio de entrada
        entry_price = 0
        try:
            # Intentar sacar de raw_data (HL o DexScreener ctx)
            if 'priceUsd' in tx.raw_data:
                entry_price = float(tx.raw_data['priceUsd'])
            elif 'px' in tx.raw_data: # Hyperliquid
                entry_price = float(tx.raw_data['px'])
            else:
                # Fallback: Precio actual de mercado
                price = fetch_current_price(symbol)
                entry_price = float(price) if price else 0
        except: pass
        
        if entry_price <= 0: return # No simular si no tenemos precio (evita ruidos)
        
        # 5. Capturar Contexto y Score Predictivo
        from .whale_intelligence import fetch_market_context
        context = fetch_market_context(symbol)
        
        predictive_score = WhaleAnalysisEngine.get_predictive_score(wallet.id, symbol, context)

        # 6. Crear la simulación (ShadowTrade)
        ShadowTrade.objects.create(
            wallet=wallet,
            token_symbol=symbol,
            entry_price=entry_price,
            amount=1.0, 
            status='OPEN',
            market_context=context 
        )
        logger.info(f"ShadowTrade AUTO creado para {wallet.name or wallet.address[:8]} en {symbol} @ {entry_price} (Score: {predictive_score})")

        # 7. Detección de Consenso de Cohorte
        cohort_others = PatternEngine._check_cohort_consensus(symbol, wallet.id)
        # 8. Generar Insight
        confidence = predictive_score
        pattern = "ACTIVIDAD"
        
        if is_consensus:
             pattern = "CONSENSO DE COHORTE"
             description = f"¡ALERTA ALPHA! {cohort_others + 1} ballenas han operado {symbol} recientemente."
             confidence = min(0.95, confidence + 0.2)
        else:
             pattern = "ACTIVIDAD INDIVIDUAL"
             description = f"La ballena inició una posición en {symbol}."
             if confidence > 0.7:
                 pattern = "MOVIMIENTO ESTRATÉGICO"
                 description = f"Movimiento de alta confianza detectado en {symbol}."

        # Guardar el insight
        meta_data = {
            'hot_token_symbol': symbol,
            'is_consensus': is_consensus,
            'cohort_size': cohort_others + 1,
            'predictive_score': predictive_score
        }
        
        insight, created = PatternInsight.objects.update_or_create(
            wallet=wallet,
            pattern_type=pattern,
            defaults={
                'description': description,
                'confidence': confidence,
                'detected_at': timezone.now(),
                'meta_data': meta_data
            }
        )
        
        # 9. Alerta Inteligente
        if confidence >= 0.7 or is_consensus:
            send_alert = False
            if created or is_consensus: 
                send_alert = True
            else:
                last_alert = insight.meta_data.get('last_alert_at') if insight.meta_data else None
                if not last_alert:
                    send_alert = True
                else:
                    from datetime import datetime
                    try:
                        last_alert_dt = datetime.fromisoformat(last_alert)
                        if (timezone.now() - last_alert_dt).total_seconds() > 14400: # 4 horas
                            send_alert = True
                    except: send_alert = True
            
            if send_alert:
                wallet_name = wallet.name or f"Ballena {wallet.address[:8]}"
                category = wallet.get_wallet_category_display()
                prob_txt = f"{round(confidence * 100)}%"
                
                msg = (
                    f"{'🔥' if is_consensus else '🐋'} <b>{'¡ALERTA DE CONSENSO!' if is_consensus else 'ALERTA DE BALLENA'}</b>\n\n"
                    f"👤 <b>Billetera:</b> {wallet_name} ({category})\n"
                    f"🌐 <b>Red:</b> {wallet.blockchain.upper()}\n"
                    f"🎯 <b>Token:</b> {symbol}\n"
                    f"📊 <b>Probabilidad Éxito:</b> <code>{prob_txt}</code>\n"
                    f"📈 <b>Patrón:</b> {pattern}\n"
                    f"📝 <b>Detalle:</b> {description}\n\n"
                    f"💡 <i>Este movimiento coincide con el ADN histórico de la ballena.</i>" if confidence > 0.75 and not is_consensus else ""
                )
                
                from .utils.notifications import send_telegram_message
                if send_telegram_message(msg):
                    if not insight.meta_data: insight.meta_data = {}
                    insight.meta_data['last_alert_at'] = timezone.now().isoformat()
                    insight.save()
        
        return f"Patrón detectado: {pattern}"

    @staticmethod
    def get_hot_tokens(hours=24):
        """Agrega el interés de todas las ballenas para encontrar tokens tendencia."""
        from datetime import timedelta
        since = timezone.now() - timedelta(hours=hours)
        
        # Filtramos insights recientes
        insights = PatternInsight.objects.filter(detected_at__gte=since)
        
        counts = {} # {symbol: {'mint': mint, 'count': sets_of_wallets}}
        
        for ins in insights:
            if not ins.meta_data: continue
            symbol = ins.meta_data.get('hot_token_symbol')
            mint = ins.meta_data.get('hot_token_mint')
            if symbol and symbol != "Unknown":
                if symbol not in counts:
                    counts[symbol] = {'mint': mint, 'wallets': set()}
                counts[symbol]['wallets'].add(ins.wallet_id)
        
        # Convertir a lista y ordenar
        hot_list = []
        for symbol, data in counts.items():
            hot_list.append({
                'symbol': symbol,
                'mint': data['mint'],
                'count': len(data['wallets'])
            })
            
        return sorted(hot_list, key=lambda x: x['count'], reverse=True)[:5]
# En services.py - agregar al final

from .whale_scoring import WhaleScoringEngine, WhalePerformanceTracker

def get_whale_score(wallet_obj):
    """
    Helper para obtener score de una ballena.
    """
    engine = WhaleScoringEngine()
    return engine.calculate_score(wallet_obj)

def get_top_scored_whales(limit=5, min_trades=3):
    """
    Helper para obtener top ballenas por score.
    """
    return WhaleScoringEngine.get_top_whales(limit=limit, min_trades=min_trades)

def update_all_whale_scores():
    """
    Actualiza scores para todas las ballenas activas.
    Útil para ejecutar en cron.
    """
    from .models import WhaleWallet
    
    wallets = WhaleWallet.objects.filter(is_active=True)
    results = []
    
    for wallet in wallets:
        score_data = WhaleScoringEngine.calculate_score(wallet)
        results.append({
            'wallet_id': wallet.id,
            'name': wallet.name,
            'score': score_data['score'],
            'category': score_data['category']['name']
        })
    
    # Ordenar por score
    results.sort(key=lambda x: x['score'], reverse=True)
    
    return results

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
    
    return None