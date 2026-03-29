import requests
import os
import json
import time
from datetime import datetime
from django.utils import timezone
from .models import WhaleWallet, WhaleTransaction, PatternInsight, ShadowTrade
from .utils.notifications import send_telegram_message

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
                    print(f"Error ctx EVM: {e}")
                
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
            print(f"[EVM Tracker Error] {e}")
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
            print(f"[Hyperliquid Tracker Error] {e}")
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
        """Analiza las transacciones de una billetera para detectar patrones y tokens específicos."""
        txs = wallet_obj.transactions.order_by('-timestamp')[:50]
        if txs.count() < 2:
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
                    if not raw or 'meta' not in raw: continue
                    
                    # Lógica original de Solana basada en balances
                    pre_balances = {b['mint']: b['uiTokenAmount']['uiAmount'] or 0 
                                   for b in raw['meta'].get('preTokenBalances', []) 
                                   if b.get('owner') == wallet_obj.address}
                    
                    post_balances = {b['mint']: b['uiTokenAmount']['uiAmount'] or 0 
                                    for b in raw['meta'].get('postTokenBalances', []) 
                                    if b.get('owner') == wallet_obj.address}
                    
                    for mint, post_val in post_balances.items():
                        pre_val = pre_balances.get(mint, 0)
                        change = post_val - pre_val
                        if change > 0:
                            # Filtrado STRICT Dinamico o Estático
                            if wallet_obj.filter_mode == 'STRICT':
                                if mint not in ESTABLISHED_TOKENS:
                                    # Si no es establecido, verificar reputación dinámica
                                    if not PatternEngine.is_token_reputable(None, mint, 'solana'):
                                        continue
                                
                            token_symbol = PatternEngine.get_token_symbol(mint)
                            
                            # Intentar capturar contexto de mercado si no lo tiene
                            if 'market_context' not in raw:
                                try:
                                    if token_symbol and not token_symbol.endswith("..."):
                                        from dashboard.whale_intelligence import fetch_market_context
                                        mkt_ctx = fetch_market_context(token_symbol)
                                        if mkt_ctx:
                                            raw['market_context'] = mkt_ctx
                                            tx.raw_data = raw
                                            # Actualizar también los campos base si estaban vacíos
                                            if tx.tx_type == "UNKNOWN":
                                                tx.tx_type = "SWAP"
                                                tx.to_asset = token_symbol
                                            tx.save()
                                except: pass
                                    
                            if mint not in token_stats:
                                token_stats[mint] = {'buys': 0, 'volume': 0}
                            token_stats[mint]['buys'] += 1
                            token_stats[mint]['volume'] += change

                            # --- AUTOMATIZACIÓN: Crear ShadowTrade ---
                            PatternEngine._automated_shadow_trade(wallet_obj, token_symbol, tx)

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
            except:
                continue
                
        # ... resto del método analyze_wallet ...
        # (Añadir al final de la clase)

    @staticmethod
    def _automated_shadow_trade(wallet, symbol, tx):
        """Crea una simulación automática si no existe una reciente para este par."""
        from django.db.models import Q
        from datetime import timedelta
        
        # 1. Ignorar Stablecoins conocidos
        STABLES = ['USDC', 'USDT', 'DAI', 'PYUSD', 'UST']
        if not symbol or symbol.upper() in STABLES: return
        
        # 2. Evitar duplicados: verificar si ya hay un trade OPEN para este wallet+token
        # NOTA: No comparar tiempos porque created_at (server time) y tx.timestamp (on-chain time) pueden desfasarse
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
        
        # 4. Crear la simulación (ShadowTrade)
        ShadowTrade.objects.create(
            wallet=wallet,
            token_symbol=symbol,
            entry_price=entry_price,
            amount=1.0, # Cantidad unitaria para simulación estadística
            status='OPEN',
            # Forzamos la fecha para que coincida con la transaccion analizada
            # NOTA: created_at es auto_now_add, así que ShadowTrade se guardará con la fecha del server
            # pero podemos usar el timestamp de la transacción para el registro inicial si fuera editable.
        )
        print(f"DEBUG: ShadowTrade AUTO creado para {wallet.name or wallet.address[:8]} en {symbol}")
                
        # Encontrar el token más "caliente" (más compras)
        hot_token = None
        max_buys = 0
        hot_token_mint = None
        
        if token_stats:
            hot_token_mint = max(token_stats, key=lambda k: token_stats[k]['buys'])
            max_buys = token_stats[hot_token_mint]['buys']
            hot_token = PatternEngine.get_token_symbol(hot_token_mint)
            
        confidence = 0.5
        pattern = "OBSERVACIÓN"
        description = "La billetera está bajo observación inicial."
        
        if hot_token:
            if max_buys > 15:
                pattern = "ACUMULACIÓN AGRESIVA"
                description = f"Esta ballena está acumulando fuertemente el token {hot_token}."
                confidence = 0.9
            elif max_buys > 5:
                pattern = "ACUMULACIÓN (DCA)"
                description = f"Patrón de compras progresivas detectado en {hot_token}."
                confidence = 0.75
            else:
                description = f"Actividad reciente detectada en el token {hot_token}."
        elif wallet_obj.filter_mode == 'STRICT':
             description = "Actividad detectada, pero ignorada por filtros de seguridad (Pump Tokens)."
             pattern = "FILTRADO"
             confidence = 0.1
                
        # Guardar el insight
        # Aseguramos que hot_token no sea None para poder filtrar
        meta_data = {
            'hot_token_mint': hot_token_mint if hot_token else "Unknown",
            'hot_token_symbol': hot_token if hot_token else "Unknown",
            'buys_count': max_buys
        }
        
        insight, created = PatternInsight.objects.update_or_create(
            wallet=wallet_obj,
            pattern_type=pattern,
            defaults={
                'description': description,
                'confidence': confidence,
                'detected_at': timezone.now(),
                'meta_data': meta_data
            }
        )
        
        # Enviar alerta de Telegram si la confianza es alta y es nuevo o han pasado más de 6 horas
        if confidence >= 0.75:
            send_alert = False
            if created:
                send_alert = True
            else:
                # Evitar spam: solo si el patrón cambió o ha pasado tiempo
                last_alert = insight.meta_data.get('last_alert_at') if insight.meta_data else None
                if not last_alert:
                    send_alert = True
                else:
                    last_alert_dt = datetime.fromisoformat(last_alert)
                    if (timezone.now() - last_alert_dt).total_seconds() > 21600: # 6 horas
                        send_alert = True
            
            if send_alert:
                wallet_name = wallet_obj.name or f"Ballena {wallet_obj.address[:8]}"
                category = wallet_obj.get_wallet_category_display()
                
                # Link dinámico según red
                explorers = {
                    'solana': f"https://solscan.io/account/{wallet_obj.address}",
                    'ethereum': f"https://etherscan.io/address/{wallet_obj.address}",
                    'base': f"https://basescan.org/address/{wallet_obj.address}",
                }
                explorer_url = explorers.get(wallet_obj.blockchain, explorers['solana'])
                explorer_name = "Solscan" if wallet_obj.blockchain == 'solana' else "Explorer"

                msg = (
                    f"🐋 <b>¡ALERTA DE BALLENA DETECTADA!</b>\n\n"
                    f"👤 <b>Billetera:</b> {wallet_name}\n"
                    f"🏷️ <b>Categoría:</b> {category}\n"
                    f"🌐 <b>Red:</b> {wallet_obj.blockchain.upper()}\n"
                    f"🎯 <b>Token:</b> {hot_token if hot_token else 'Varios'}\n"
                    f"📈 <b>Patrón:</b> {pattern}\n"
                    f"📝 <b>Detalle:</b> {description}\n\n"
                    f"🔗 <a href='{explorer_url}'>Ver en {explorer_name}</a>\n"
                    f"💡 <i>Analizado por CriptoDash PatternEngine</i>"
                )
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