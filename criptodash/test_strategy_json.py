import os, django, json
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')
django.setup()

from dashboard.pair_scanner import fetch_ohlcv_df, _get_exchange
from dashboard.scalping_strategies import run_strategy

exchange = _get_exchange()
df = fetch_ohlcv_df(exchange, 'BTC/USDT', '15m', limit=250)

for strat in ['EMA_CROSS', 'BB_SQUEEZE', 'VWAP_RSI']:
    try:
        res = run_strategy(strat, df)
        json.dumps(res)
        print(f"OK {strat} | signal={res['signal']} conf={res['confidence']}")
    except Exception as e:
        print(f"ERROR {strat}: {e}")
