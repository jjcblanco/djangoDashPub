import os
import django
import sys

sys.path.append(r'C:\Users\Javier\Desktop\programacion\djangoDashPub\criptodash')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')
django.setup()

from dashboard.models import WhaleWallet
w = WhaleWallet.objects.get(id=1)
print(f"Address: {w.address} | Blockchain: {w.blockchain}")
