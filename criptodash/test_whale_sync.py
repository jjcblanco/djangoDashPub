import os
import sys
import django
from datetime import datetime

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')
django.setup()

from dashboard.models import WhaleWallet
from dashboard.services import SolanaWhaleTracker, PatternEngine

def test_sync(address):
    wallet, created = WhaleWallet.objects.get_or_create(
        address=address,
        defaults={'name': 'Test Wallet', 'blockchain': 'solana'}
    )
    
    tracker = SolanaWhaleTracker()
    print(f"Syncing wallet: {address}...")
    new_txs = tracker.sync_wallet(wallet)
    print(f"New transactions found: {new_txs}")
    
    # Ver cuantas transacciones tiene ahora
    count = wallet.transactions.count()
    print(f"Total transactions in DB: {count}")
    
    # Ejecutar análisis
    print("Running analysis...")
    result = PatternEngine.analyze_wallet(wallet)
    print(f"Analysis result: {result}")
    
    # Ver si se creó el insight
    from dashboard.models import PatternInsight
    insight = PatternInsight.objects.filter(wallet=wallet).first()
    if insight:
        print(f"Insight created: {insight.pattern_type} - {insight.description}")
    else:
        print("No insight created.")

if __name__ == "__main__":
    test_address = "3xqUaVuAWsppb8yaSPJ2hvdvfjteMq2EbdCc3CLguaTE"
    test_sync(test_address)
