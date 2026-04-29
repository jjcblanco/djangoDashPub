import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')
django.setup()

from dashboard.models import ScalpingBot
from dashboard.pair_scanner import fetch_ohlcv_df, _get_exchange

bots = ScalpingBot.objects.all()
for b in bots:
    print(f"Bot {b.id}: {b.name}, Symbol: '{b.pair.symbol}', Timeframe: '{b.timeframe}', Status: {b.status}, Error: {b.last_error}")

# Let's try to fetch ETH/USDT 
exc = _get_exchange()
df = fetch_ohlcv_df(exc, 'ETH/USDT', '5m', limit=250)
print("ETH/USDT 5m df len:", len(df) if df is not None else "None")
