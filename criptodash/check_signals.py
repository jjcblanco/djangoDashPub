import os
import django
import sys

# Add the project directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')
django.setup()

from dashboard.models import TradeSignal, TradingPair

def check_signals():
    print('TradeSignal count:', TradeSignal.objects.count())
    print('TradingPair count:', TradingPair.objects.count())

    if TradingPair.objects.filter(symbol='ETH/USDT').exists():
        pair = TradingPair.objects.get(symbol='ETH/USDT')
        signals = TradeSignal.objects.filter(pair=pair)
        print('ETH/USDT signals count:', signals.count())
        print('Sample signals:', list(signals.values('timestamp', 'signal_type')[:5]))

        # Check for signals in the date range
        from django.utils import timezone
        from datetime import datetime
        try:
            fecha_inicio_dt = timezone.make_aware(datetime.strptime('2025-11-26', '%Y-%m-%d'))
            fecha_fin_dt = timezone.make_aware(datetime.strptime('2025-11-29', '%Y-%m-%d'))
            signals_in_range = signals.filter(timestamp__gte=fecha_inicio_dt, timestamp__lt=fecha_fin_dt)
            print('Signals in date range 2025-11-26 to 2025-11-29:', signals_in_range.count())
        except Exception as e:
            print('Error checking date range:', e)
    else:
        print('ETH/USDT pair not found')

if __name__ == '__main__':
    check_signals()
