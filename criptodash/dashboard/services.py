import requests
import json
import time
from datetime import datetime
from django.utils import timezone
from .models import WhaleWallet, WhaleTransaction, PatternInsight

class SolanaWhaleTracker:
    def __init__(self, rpc_url="https://api.mainnet-beta.solana.com"):
        self.rpc_url = rpc_url

    def get_transactions(self, address, limit=10):
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getSignaturesForAddress",
            "params": [
                address,
                {"limit": limit}
            ]
        }
        response = requests.post(self.rpc_url, json=payload)
        return response.json().get('result', [])

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
        response = requests.post(self.rpc_url, json=payload)
        return response.json().get('result', {})

    def sync_wallet(self, wallet_obj):
        signatures = self.get_transactions(wallet_obj.address)
        new_txs = 0
        
        for sig in signatures:
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
            time.sleep(0.5) # Avoid rate limiting
            
        return new_txs

class PatternEngine:
    @staticmethod
    def analyze_wallet(wallet_obj):
        txs = wallet_obj.transactions.order_by('timestamp')
        if not txs.exists():
            return "No hay transacciones suficientes para analizar."
            
        # Placeholder for complex pattern logic
        # Ej: Si hay muchos depósitos seguidos sin ventas = Acumulación
        
        insight_msg = f"Análisis de {wallet_obj.name or wallet_obj.address[:8]}: "
        # ... lógica de detección ...
        
        return insight_msg
