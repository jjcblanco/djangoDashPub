import os
import django
import sys
import json

sys.path.append(r'C:\Users\Javier\Desktop\programacion\djangoDashPub\criptodash')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')
django.setup()

from dashboard.models import WhaleTransaction

tx = WhaleTransaction.objects.filter(wallet_id=1, tx_type='UNKNOWN').first()
if tx:
    print(f"TX Hash: {tx.tx_hash}")
    print(f"Raw Data Keys: {list(tx.raw_data.keys()) if tx.raw_data else 'None'}")
    if tx.raw_data and 'meta' in tx.raw_data:
        print("Meta found!")
        print(f"Pre Token Balances: {len(tx.raw_data['meta'].get('preTokenBalances', []))}")
        print(f"Post Token Balances: {len(tx.raw_data['meta'].get('postTokenBalances', []))}")
    else:
        print("Meta NOT found in raw_data")
        # print(json.dumps(tx.raw_data, indent=2)[:1000]) # Solo los primeros 1000 char
else:
    print("No UNKNOWN transactions found.")
