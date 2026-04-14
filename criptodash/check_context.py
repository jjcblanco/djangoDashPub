import os
import sys
import django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')
django.setup()
from dashboard.models import ShadowTrade
for t in ShadowTrade.objects.all():
    print(f'Trade {t.id}: {t.token_symbol}, PnL {t.pnl_percent}%')
    if t.market_context:
        for k, v in t.market_context.items():
            print(f'  {k}: {v}')
    else:
        print('  No context')
    print()