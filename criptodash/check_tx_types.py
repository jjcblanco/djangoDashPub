import os
import django
import sys

sys.path.append(r'C:\Users\Javier\Desktop\programacion\djangoDashPub\criptodash')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')
django.setup()

from dashboard.models import WhaleTransaction
from django.db.models import Count

res = WhaleTransaction.objects.filter(wallet_id=1).values('tx_type').annotate(count=Count('id'))
print("Transaction Types for Wallet 1:")
for r in res:
    print(f"{r['tx_type']}: {r['count']}")
