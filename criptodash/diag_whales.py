import os
import django
import sys

# Añadir el path del proyecto
sys.path.append(r'C:\Users\Javier\Desktop\programacion\djangoDashPub\criptodash')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')
django.setup()

from dashboard.models import WhaleWallet, WhaleTransaction

wallets = WhaleWallet.objects.all()
print(f"Total Wallets: {wallets.count()}")
for w in wallets:
    tx_count = w.transactions.count()
    print(f"ID: {w.id} | Name: {w.name} | Status: {w.sync_status} | Last Sync: {w.last_sync} | TXs: {tx_count}")
