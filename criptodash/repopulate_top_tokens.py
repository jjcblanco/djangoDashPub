import os
import django
import sys

sys.path.append(r'C:\Users\Javier\Desktop\programacion\djangoDashPub\criptodash')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')
django.setup()

from dashboard.models import WhaleWallet
from dashboard.services import PatternEngine

wallets = WhaleWallet.objects.filter(is_active=True)
print(f"Re-analyzing {wallets.count()} wallets...")

for wallet in wallets:
    print(f"Analyzing {wallet.name or wallet.address}...")
    PatternEngine.analyze_wallet(wallet)
    wallet.refresh_from_db()
    print(f"  - Top Tokens: {wallet.top_tokens}")

print("Done!")
