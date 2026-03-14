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
        """Analiza las transacciones de una billetera para detectar patrones de comportamiento."""
        txs = wallet_obj.transactions.order_by('-timestamp')[:50] # Analizamos las últimas 50
        if txs.count() < 5:
            return "Datos insuficientes"
            
        # Contadores básicos
        swaps_in = 0
        swaps_out = 0
        total_volume = 0
        
        # Lógica de detección simplificada
        for tx in txs:
            # Intentar identificar si es compra o venta por los balances (placeholder mejorado)
            # En una implementación real, analizaríamos postTokenBalances del RPC
            if "buy" in str(tx.raw_data).lower() or "swap" in str(tx.raw_data).lower():
                swaps_in += 1
            
        confidence = 0.5
        pattern = "OBSERVACIÓN"
        description = "La billetera está bajo observación inicial."
        
        if swaps_in > 15:
            pattern = "ACUMULACIÓN AGRESIVA"
            description = "Esta ballena está acumulando activos de forma constante en cortos periodos de tiempo."
            confidence = 0.85
        elif swaps_in > 5:
            pattern = "ACUMULACIÓN (DCA)"
            description = "Patrón de compras regulares detectado. Típicamente indica confianza a largo plazo."
            confidence = 0.7
            
        # Guardar el insight en la base de datos
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
