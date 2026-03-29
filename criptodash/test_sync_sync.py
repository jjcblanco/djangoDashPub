import os
import django
import sys

# Añadir el path del proyecto
sys.path.append(r'C:\Users\Javier\Desktop\programacion\djangoDashPub\criptodash')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')
django.setup()

from dashboard.tasks import sync_wallet_task
from dashboard.models import WhaleWallet

wallet_id = 1
print(f"Executing sync_wallet_task for wallet {wallet_id} synchronously...")

try:
    # Llamamos a la función directamente (no .delay()) para que corra en este proceso
    result = sync_wallet_task(wallet_id, deep_sync=True)
    print(f"Task result: {result}")
    
    w = WhaleWallet.objects.get(id=wallet_id)
    print(f"After Sync - Status: {w.sync_status} | Last Sync: {w.last_sync} | TXs: {w.transactions.count()}")
except Exception as e:
    print(f"Error during sync: {e}")
    import traceback
    traceback.print_exc()
