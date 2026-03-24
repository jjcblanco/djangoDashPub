import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')
sys.path.append(os.getcwd())
django.setup()

from dashboard.models import WhaleTransaction
from dashboard.whale_intelligence import fetch_market_context

def backfill():
    # Solo transacciones que tengan un asset de destino y no tengan contexto aún
    txs = WhaleTransaction.objects.filter(raw_data__isnull=False).order_by('-timestamp')
    count = 0
    updated = 0
    
    print(f"Buscando contexto para {txs.count()} transacciones...")
    
    for tx in txs:
        raw = tx.raw_data
        if not isinstance(raw, dict): 
            print(f"Skipping TX {tx.id} - raw_data is not dict: {type(raw)}")
            continue
        
        if 'market_context' not in raw:
            symbol = tx.to_asset or tx.from_asset
            print(f"TX {tx.id}: Symbol={symbol}, Keys={list(raw.keys())}")
            if symbol and symbol != 'UNKNOWN':
                print(f"Procesando {symbol} ({tx.tx_hash[:10]})...")
                mkt_ctx = fetch_market_context(symbol)
                if mkt_ctx:
                    raw['market_context'] = mkt_ctx
                    tx.raw_data = raw
                    tx.save()
                    updated += 1
                    print(f"  [OK] Contexto guardado para {symbol}")
                else:
                    print(f"  [SKIP] No se pudo obtener contexto para {symbol}")
        count += 1
        if updated >= 20: # Limitar para no saturar APIs en el primer test
            print("Límite de 20 actualizaciones alcanzado en este lote.")
            break

    print(f"Proceso terminado. Actualizados: {updated}")

if __name__ == "__main__":
    backfill()
