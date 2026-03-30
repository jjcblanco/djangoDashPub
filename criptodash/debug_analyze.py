import os
import django
import sys
import json

sys.path.append(r'C:\Users\Javier\Desktop\programacion\djangoDashPub\criptodash')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')
django.setup()

from dashboard.models import WhaleWallet, WhaleTransaction
from dashboard.services import PatternEngine

wallet_id = 1
wallet = WhaleWallet.objects.get(id=wallet_id)
txs = wallet.transactions.filter(tx_type='UNKNOWN')

print(f"Analyzing {txs.count()} UNKNOWN transactions for wallet {wallet.address}...")

for tx in txs:
    print(f"\nChecking TX {tx.tx_hash}:")
    raw = tx.raw_data
    if not raw or 'meta' not in raw:
        print("  - No meta found")
        continue
    
    pre_all = raw['meta'].get('preTokenBalances', [])
    post_all = raw['meta'].get('postTokenBalances', [])
    
    print(f"  - Total Pre/Post Token Balances: {len(pre_all)}/{len(post_all)}")
    
    pre_balances = {b['mint']: b['uiTokenAmount']['uiAmount'] or 0 
                   for b in pre_all 
                   if b.get('owner') == wallet.address}
    
    post_balances = {b['mint']: b['uiTokenAmount']['uiAmount'] or 0 
                    for b in post_all 
                    if b.get('owner') == wallet.address}
    
    print(f"  - Filtered Pre/Post for Wallet: {len(pre_balances)}/{len(post_balances)}")
    if len(post_balances) == 0:
        if len(post_all) > 0:
            print(f"  - Founders in post_all: {set([b.get('owner') for b in post_all])}")
    
    for mint, post_val in post_balances.items():
        pre_val = pre_balances.get(mint, 0)
        change = post_val - pre_val
        print(f"  - Mint: {mint} | Change: {change}")
        if change > 0:
            print("  - BUY DETECTED!")
