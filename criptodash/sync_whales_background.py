import os
import time
import django
from datetime import datetime

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')
django.setup()

from dashboard.models import WhaleWallet
from dashboard.services import SolanaWhaleTracker, PatternEngine

def run_full_sync():
    print(f"[{datetime.now()}] Iniciando Sincronización Completa de Ballenas...")
    wallets = WhaleWallet.objects.filter(is_active=True)
    tracker = SolanaWhaleTracker()
    
    for wallet in wallets:
        print(f"\n--- Sincronizando: {wallet.name or wallet.address} ({wallet.blockchain}) ---")
        try:
            # En script de fondo no nos importa el timeout, bajamos hasta 50
            new_txs = tracker.sync_wallet(wallet, max_new=50)
            print(f"[OK] {new_txs} nuevas transacciones encontradas.")
            
            # Analizar
            result = PatternEngine.analyze_wallet(wallet)
            print(f"[Análisis] {result}")
        except Exception as e:
            print(f"[ERROR] Falló sincronización de {wallet.address}: {e}")
            
    print(f"\n[{datetime.now()}] Sincronización finalizada.")

if __name__ == "__main__":
    run_full_sync()
