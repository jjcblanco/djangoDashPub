import os
import django
import datetime
from django.utils import timezone

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')
django.setup()

from dashboard.models import TradeSignal, TradingPair
from django.db.models import Count, Max

def audit():
    print(f"--- DATABASE AUDIT ({timezone.now()}) ---")
    pairs = TradingPair.objects.all()
    for p in pairs:
        print(f"\n[{p.symbol}] (ID: {p.id})")
        # Por temporalidad
        stats = TradeSignal.objects.filter(pair=p).values('timeframe').annotate(
            total=Count('id'),
            latest=Max('timestamp')
        ).order_by('timeframe')
        
        if not stats:
            print("  No signals found for this pair.")
            continue
            
        for s in stats:
            print(f"  TF: {s['timeframe']:>3} | Count: {s['total']:>6} | Latest: {s['latest']}")

if __name__ == "__main__":
    audit()
