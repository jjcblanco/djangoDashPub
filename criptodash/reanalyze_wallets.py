import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')
sys.path.append(os.getcwd())
django.setup()

from dashboard.models import WhaleWallet
from dashboard.services import PatternEngine

def reanalyze():
    wallets = WhaleWallet.objects.all()
    print(f"Re-analizando {wallets.count()} billeteras...")
    
    for wallet in wallets:
        print(f"Procesando {wallet.address[:10]} ({wallet.blockchain})...")
        result = PatternEngine.analyze_wallet(wallet)
        print(f"  Resultado: {result}")

if __name__ == "__main__":
    reanalyze()
