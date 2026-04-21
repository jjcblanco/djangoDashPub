import os
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')
django.setup()

from dashboard.pair_scanner import fetch_ohlcv_df, _get_exchange
from dashboard.scalping_strategies import run_strategy

print("Iniciando test de estrategias...")
exchange = _get_exchange()
df = fetch_ohlcv_df(exchange, 'DOGE/USDT', '15m', limit=100)

for strat in ['EMA_CROSS', 'BB_SQUEEZE', 'VWAP_RSI']:
    try:
        res = run_strategy(strat, df)
        # Probamos la serializacion
        json.dumps(res)
        print(f"OK {strat} Serializa correctamente")
    except Exception as e:
        print(f"ERROR {strat} FALLA en serializacion:")
        print(e)
