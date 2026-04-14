import os
import sys
import django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')
django.setup()
from dashboard.whale_intelligence import fetch_market_context
context = fetch_market_context('SOL')
if context:
    for k, v in context.items():
        print(f'{k}: {v}')
else:
    print('No context returned')