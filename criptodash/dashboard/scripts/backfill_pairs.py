# scripts/backfill_pairs.py
import django, os, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')
django.setup()
from dashboard.models import Pair
from trading_bot.models import TradingSignal

# Supón que TradingSignal tenía un campo 'symbol' viejo (string)
symbols = TradingSignal.objects.values_list('symbol', flat=True).distinct()
for s in symbols:
    if not s:
        continue
    p, _ = Pair.objects.get_or_create(symbol=s, defaults={'base_asset': s.split('/')[0]})
    TradingSignal.objects.filter(symbol=s, pair__isnull=True).update(pair=p)