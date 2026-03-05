
import os
import sys
import django
import pandas as pd
import ccxt

# Agregar el directorio del proyecto al path
sys.path.append(r'c:\Users\Javier\Desktop\programacion\djangoDashPub\criptodash')

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')
django.setup()

from dashboard.backtester import DayTradingStrategy

def test_late_entry():
    # Mock data showing an old crossover
    data = {
        'open': [80]*5 + [90]*5,
        'high': [85]*5 + [95]*5,
        'low': [75]*5 + [85]*5,
        'close': [82]*5 + [92]*5,
        'volume': [100]*10
    }
    df = pd.DataFrame(data)
    
    # EMAs overlap calculation happens inside strategy. 
    # Let's use real market data for a more reliable test.
    exchange = ccxt.binance()
    bars = exchange.fetch_ohlcv('SOL/USDT', timeframe='1h', limit=100)
    df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    
    print("\n--- TEST: Normal Entry (Default) ---")
    strategy_normal = DayTradingStrategy(parameters={'min_strength': '0', 'min_adx': '0'})
    df_n = strategy_normal.generate_signals(df.copy())
    print(f"Last signal (Normal): {df_n.iloc[-1]['signal']}")
    
    print("\n--- TEST: Late Entry (Enabled) ---")
    strategy_late = DayTradingStrategy(parameters={'min_strength': '0', 'min_adx': '0', 'allow_late_entry': 'true'})
    df_l = strategy_late.generate_signals(df.copy())
    last_row = df_l.iloc[-1]
    print(f"Last signal (Late): {last_row['signal']}")
    
    if last_row['signal'] == 'HOLD':
        print("\nInternal Condition Data (Last Row):")
        print(f" - EMA Aligned (ema9 > ema21): {last_row['ema9'] > last_row['ema21']}")
        print(f" - Price > EMA50: {last_row['close'] > last_row['ema50']}")
        print(f" - Price > EMA200: {last_row['close'] > last_row['ema200']}")
        print(f" - MACD > Signal: {last_row['macd'] > last_row['signal_macd']}")
        print(f" - RSI ({last_row['rsi']:.2f}) > 55: {last_row['rsi'] > 55}")
        print(f" - Use Candles: {strategy_late.parameters.get('use_candles')}")
        if strategy_late.parameters.get('use_candles'):
            print(f"   - Is Hammer: {last_row['is_hammer']}")
            print(f"   - Is Bullish Engulfing: {last_row['is_bullish_engulfing']}")
        
    print("\n--- Last 5 Signals ---")
    print(df_l[['timestamp', 'close', 'signal']].tail(5))

if __name__ == "__main__":
    test_late_entry()
