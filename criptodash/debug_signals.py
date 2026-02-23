import os
import django
import datetime
from django.utils import timezone

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')
django.setup()

from dashboard.models import TradeSignal, TradingPair
from django.db.models import Count, Max

def debug_signals():
    print(f"Current Time (Local): {datetime.datetime.now()}")
    print(f"Current Time (UTC): {timezone.now()}")
    
    pairs = TradingPair.objects.all()
    for p in pairs:
        print(f"\n--- Pair: {p.symbol} (ID: {p.id}) ---")
        counts = TradeSignal.objects.filter(pair=p).values('timeframe').annotate(
            count=Count('id'),
            latest=Max('timestamp')
        )
        for c in counts:
            print(f"  Timeframe: {c['timeframe']}, Count: {c['count']}, Latest: {c['latest']}")

if __name__ == "__main__":
    debug_signals()
