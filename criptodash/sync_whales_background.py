import os
import django
import time
import argparse
from datetime import datetime

# 1. Cargar .env manualmente (Fix para VPS)
def load_env_manually():
    try:
        # Intentar en el directorio actual o uno arriba
        env_paths = ['.env', os.path.join(os.path.dirname(__file__), '.env'), '../.env']
        found = False
        for env_path in env_paths:
            if os.path.exists(env_path):
                with open(env_path) as f:
                    for line in f:
                        if line.strip() and not line.startswith('#'):
                            if '=' in line:
                                key, value = line.strip().split('=', 1)
                                os.environ[key] = value.strip('"').strip("'")
                print(f"[OK] .env cargado desde {env_path}.")
                found = True
                break
        if not found:
            print("[!] No se encontró el archivo .env")
    except Exception as e:
        print(f"[!] Error cargando .env: {e}")

load_env_manually()

# 2. Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')
django.setup()

from dashboard.models import WhaleWallet
from dashboard.services import SolanaWhaleTracker, PatternEngine

def run_full_sync():
    print(f"\n[{datetime.now()}] --- Iniciando Sincronización Completa ---")
    wallets = WhaleWallet.objects.filter(is_active=True)
    from dashboard.services import SolanaWhaleTracker, EVMWhaleTracker, PatternEngine
    
    total_new = 0
    for wallet in wallets:
        print(f"Sincronizando: {wallet.name or wallet.address[:8]} ({wallet.blockchain})...")
        try:
            if wallet.blockchain == 'solana':
                tracker = SolanaWhaleTracker()
                new_txs = tracker.sync_wallet(wallet, max_new=50)
            elif wallet.blockchain in ['ethereum', 'base']:
                tracker = EVMWhaleTracker(wallet.blockchain)
                new_txs = tracker.sync_wallet(wallet, max_new=100)
            else:
                print(f"  [SKIP] Red no soportada: {wallet.blockchain}")
                continue
                
            total_new += new_txs
            # Analizar patrones
            PatternEngine.analyze_wallet(wallet)
        except Exception as e:
            print(f"  [ERROR] {wallet.address[:8]}: {e}")
            
    print(f"[{datetime.now()}] Sincronización finalizada. Total nuevas txs: {total_new}")
    return total_new

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Script de sincronización de ballenas.')
    parser.add_argument('--loop', action='store_true', help='Ejecutar en bucle infinito')
    parser.add_argument('--interval', type=int, default=600, help='Intervalo en segundos (default: 600s)')
    
    args = parser.parse_args()
    
    if args.loop:
        print(f"MODO SERVICIO ACTIVO: Sincronizando cada {args.interval} segundos.")
        try:
            while True:
                run_full_sync()
                print(f"Esperando {args.interval}s para el próximo ciclo...")
                time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\nDeteniendo el seguidor de ballenas...")
    else:
        # Ejecución única
        run_full_sync()
