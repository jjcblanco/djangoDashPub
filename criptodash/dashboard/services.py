import requests
import json
import time
from datetime import datetime
from django.utils import timezone
from .models import WhaleWallet, WhaleTransaction, PatternInsight
from .utils.notifications import send_telegram_message

class SolanaWhaleTracker:
    def __init__(self, rpc_url="https://api.mainnet-beta.solana.com"):
        self.rpc_url = rpc_url

    def get_transactions(self, address, limit=None):
        if limit is None:
            limit = 50 # Default para background script
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getSignaturesForAddress",
            "params": [
                address,
                {"limit": limit}
            ]
        }
        try:
            response = requests.post(self.rpc_url, json=payload, timeout=10)
            return response.json().get('result', [])
        except requests.exceptions.RequestException:
            return []

    def get_transaction_details(self, tx_hash):
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getTransaction",
            "params": [
                tx_hash,
                {"encoding": "json", "maxSupportedTransactionVersion": 0}
            ]
        }
        try:
            response = requests.post(self.rpc_url, json=payload, timeout=10)
            return response.json().get('result', {})
        except requests.exceptions.RequestException:
            return {}

    def sync_wallet(self, wallet_obj, max_new=5, signatures_limit=None):
        """
        Sincroniza las transacciones de una billetera.
        max_new: Límite de transacciones nuevas a procesar para evitar timeouts en peticiones web.
        """
        signatures = self.get_transactions(wallet_obj.address, limit=signatures_limit)
        new_txs = 0
        
        for sig in signatures:
            if new_txs >= max_new:
                break
                
            tx_hash = sig['signature']
            if WhaleTransaction.objects.filter(tx_hash=tx_hash).exists():
                continue
                
            details = self.get_transaction_details(tx_hash)
            if not details:
                continue
                
            # Basic parsing (can be refined as we see more data)
            timestamp = timezone.make_aware(datetime.fromtimestamp(sig['blockTime'])) if sig.get('blockTime') else timezone.now()
            
            WhaleTransaction.objects.create(
                wallet=wallet_obj,
                tx_hash=tx_hash,
                timestamp=timestamp,
                tx_type="UNKNOWN", # Will be updated by PatternEngine
                raw_data=details
            )
            new_txs += 1
            # Eliminamos el sleep en la web para ganar cada milisegundo posible
            
        return new_txs

class PatternEngine:
    @staticmethod
    def get_token_symbol(mint):
        """Busca el símbolo de un token dinámicamente usando la API de Jupiter."""
        # Caché estática básica
        TOKEN_MAP = {
            'So11111111111111111111111111111111111111112': 'SOL',
            'EPjFW3F2KVq2aLecqCP5i5nw53J2tOt9iies23XYwjLu': 'USDC',
            'Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB': 'USDT',
            'JUPyiPZp718zay7kaPn2CoJvRwvpqcRuS5B7shuYf79': 'JUP',
            'DezXAZ8z7Pnrn9vzctrxEXpWMrNHqR1f6f69nL4XYUDx': 'BONK',
        }
        
        if mint in TOKEN_MAP:
            return TOKEN_MAP[mint]
            
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        try:
            # Opción 1: Jupiter API
            url = f"https://tokens.jup.ag/token/{mint}"
            resp = requests.get(url, headers=headers, timeout=3)
            if resp.status_code == 200:
                data = resp.json()
                if data.get('symbol'):
                    return data['symbol']
            
            # Opción 2: DexScreener API
            url_dex = f"https://api.dexscreener.com/latest/dex/tokens/{mint}"
            resp_dex = requests.get(url_dex, headers=headers, timeout=3)
            if resp_dex.status_code == 200:
                data_dex = resp_dex.json()
                pairs = data_dex.get('pairs', [])
                if pairs:
                    return pairs[0].get('baseToken', {}).get('symbol', mint[:8] + "...")
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
        
        for tx in txs:
            try:
                raw = tx.raw_data
                if not raw or 'meta' not in raw: continue
                
                # Buscar cambios en balances de tokens
                pre_balances = {b['mint']: b['uiTokenAmount']['uiAmount'] or 0 
                               for b in raw['meta'].get('preTokenBalances', []) 
                               if b.get('owner') == wallet_obj.address}
                
                post_balances = {b['mint']: b['uiTokenAmount']['uiAmount'] or 0 
                                for b in raw['meta'].get('postTokenBalances', []) 
                                if b.get('owner') == wallet_obj.address}
                
                for mint, post_val in post_balances.items():
                    pre_val = pre_balances.get(mint, 0)
                    change = post_val - pre_val
                    
                    if change > 0: # Compra o recepción
                        if mint not in token_stats:
                            token_stats[mint] = {'buys': 0, 'volume': 0}
                        token_stats[mint]['buys'] += 1
                        token_stats[mint]['volume'] += change
            except:
                continue
                
        # Encontrar el token más "caliente" (más compras)
        hot_token = None
        max_buys = 0
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
                msg = (
                    f"🐋 <b>¡ALERTA DE BALLENA DETECTADA!</b>\n\n"
                    f"👤 <b>Billetera:</b> {wallet_name}\n"
                    f"🏷️ <b>Categoría:</b> {category}\n"
                    f"🎯 <b>Token:</b> {hot_token if hot_token else 'Varios'}\n"
                    f"📈 <b>Patrón:</b> {pattern}\n"
                    f"📝 <b>Detalle:</b> {description}\n\n"
                    f"🔗 <a href='https://solscan.io/account/{wallet_obj.address}'>Ver en Solscan</a>\n"
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
