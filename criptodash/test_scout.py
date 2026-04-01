import os
import django
import sys

# Setup Django environment
sys.path.append(r'C:\Users\Javier\Desktop\programacion\djangoDashPub\criptodash')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')
django.setup()

from dashboard.services import PatternEngine

def test_scout():
    # PEPE Token on Ethereum
    pepe_address = "0x6982508145454Ce325dDbE47a25d4ec3d2311933"
    print(f"--- 📡 Escaneando Ballenas de PEPE ($ETH) ---")
    
    whales = PatternEngine.discover_token_whales(pepe_address, blockchain='ethereum')
    
    if not whales:
        print("❌ No se detectaron movimientos recientes o la API de Etherscan falló.")
        return

    print(f"✅ Descubiertas {len(whales)} ballenas activas:")
    for i, w in enumerate(whales, 1):
        print(f"{i}. Address: {w['address'][:15]}... | Volume: {w['volume']:,.0f} {w['symbol']}")

if __name__ == "__main__":
    test_scout()
