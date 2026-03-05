import os
import django
import sys

# Setup Django
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')
django.setup()

from dashboard.ccxttest1 import binance as exchange

def test_fetch_funding():
    print("--- Probando recuperación de depósitos y transferencias ---")
    
    try:
        # 1. Probar Depósitos (Fiat/Crypto externos)
        print("\nBuscando Depósitos recientes...")
        deposits = exchange.fetch_deposits()
        for d in deposits[:5]:
            print(f"Depósito: {d['amount']} {d['currency']} - Fecha: {d['datetime']} - Status: {d['status']}")
            
        # 2. Probar Transferencias (Entre Spot, Earn, Margin, etc.)
        # Nota: CCXT usa fetch_transfers si el exchange lo soporta
        print("\nBuscando Transferencias internas (Spot/Earn/etc)...")
        if exchange.has['fetchTransfers']:
            transfers = exchange.fetch_transfers()
            for t in transfers[:5]:
                print(f"Transferencia: {t['amount']} {t['currency']} - De: {t['fromAccount']} - A: {t['toAccount']} - Fecha: {t['datetime']}")
        else:
            print("El exchange (o CCXT en esta versión) no tiene habilitado fetchTransfers directamente.")
            
    except Exception as e:
        print(f"Error al recuperar datos: {e}")

if __name__ == "__main__":
    test_fetch_funding()
