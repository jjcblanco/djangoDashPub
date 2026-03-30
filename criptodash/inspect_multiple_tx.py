import os
import django
import sys
import json

sys.path.append(r'C:\Users\Javier\Desktop\programacion\djangoDashPub\criptodash')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')
django.setup()

from dashboard.models import WhaleTransaction

txs = WhaleTransaction.objects.filter(wallet_id=1, tx_type='UNKNOWN')[:5]
for i, tx in enumerate(txs):
    print(f"TX {i} Hash: {tx.tx_hash}")
    rd = tx.raw_data
    if rd and 'meta' in rd:
        pre_tk = len(rd['meta'].get('preTokenBalances', []))
        post_tk = len(rd['meta'].get('postTokenBalances', []))
        pre_sol = len(rd['meta'].get('preBalances', []))
        post_sol = len(rd['meta'].get('postBalances', []))
        print(f"  - Pre/Post Token Balances: {pre_tk}/{post_tk}")
        print(f"  - Pre/Post SOL Balances: {pre_sol}/{post_sol}")
    else:
        print(f"  - No meta found in raw_data")
