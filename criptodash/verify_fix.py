import os
import django
import sys
import json

sys.path.append(r'C:\Users\Javier\Desktop\programacion\djangoDashPub\criptodash')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')
django.setup()

from django.db.models import Count
from dashboard.models import WhaleWallet, WhaleTransaction
from dashboard.services import PatternEngine
from dashboard.whale_analysis import WhaleAnalysisEngine

wallet_id = 1
wallet = WhaleWallet.objects.get(id=wallet_id)

print(f"--- Step 1: Re-analyzing wallet {wallet.name} ---")
PatternEngine.analyze_wallet(wallet)

# Verificar tipos tras el analisis
res = WhaleTransaction.objects.filter(wallet_id=wallet_id).values('tx_type').annotate(count=Count('id'))
print("Updated Transaction Types:")
from django.db.models import Count
for r in WhaleTransaction.objects.filter(wallet_id=wallet_id).values('tx_type').annotate(count=Count('id')):
    print(f"{r['tx_type']}: {r['count']}")

print(f"\n--- Step 2: Testing suggest_bot_params ---")
suggestion = WhaleAnalysisEngine.suggest_bot_params(wallet_id)

if 'error' in suggestion:
    print(f"STILL ERROR: {suggestion['error']}")
else:
    print("SUCCESS! Suggested Bot Params:")
    print(f"Top Token: {suggestion['top_token']}")
    print(f"Grid Range: {suggestion['grid']['lower_price']} - {suggestion['grid']['upper_price']}")
    print(f"Timeframe: {suggestion['daytrading']['timeframe']}")
