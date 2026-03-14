import requests
import json
import time
from datetime import datetime
from django.utils import timezone
from .models import WhaleWallet, WhaleTransaction, PatternInsight

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
        PatternInsight.objects.update_or_create(
            wallet=wallet_obj,
            pattern_type=pattern,
            defaults={
                'description': description,
                'confidence': confidence,
                'detected_at': timezone.now()
            }
        )
        
        return f"Patrón detectado: {pattern}"
