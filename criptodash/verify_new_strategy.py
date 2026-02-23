import os
import django
import datetime
from django.utils import timezone

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')
django.setup()

from dashboard import ccxttest1
from dashboard.models import TradingPair, TradeSignal

def verify_strategy():
    pair_symbol = 'BNB/USDT'
    timeframe = '1h'
    date_from = (datetime.datetime.now() - datetime.timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')
    
    print(f"--- Verifying Strategy for {pair_symbol} ({timeframe}) ---")
    print(f"Fetching data from: {date_from}")
    
    try:
        sig_df = ccxttest1.run_bot(pair_symbol, date_from, timeframe)
        
        # Filtrar solo las filas con señales reales
        actual_signals = sig_df[sig_df['signal_buy_sell'] != 'none']
        
        print(f"\nTotal signals generated: {len(actual_signals)}")
        if not actual_signals.empty:
            print("\nLatest 5 signals:")
            print(actual_signals[['timestamp', 'close', 'signal_buy_sell', 'signal_strenght', 'adx']].tail(5))
            
            # Verificar distribución de fuerza
            print("\nStrength Distribution:")
            print(actual_signals['signal_strenght'].value_counts())
        else:
            print("\nNo signals generated with current filters.")
            # Mostrar stats de ADX para diagnosticar si el filtro es muy estricto
            print(f"\nADX Stats:")
            print(sig_df['adx'].describe())
            
    except Exception as e:
        print(f"Error during verification: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    verify_strategy()
