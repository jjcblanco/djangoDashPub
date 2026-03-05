
import os
import sys
import django
import pandas as pd
import ccxt
from datetime import datetime

# Agregar el directorio del proyecto al path
sys.path.append(r'c:\Users\Javier\Desktop\programacion\djangoDashPub\criptodash')

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')
django.setup()

from dashboard.backtester import DayTradingStrategy
from dashboard.models import LiveBot

def diagnostic():
    bot_name = 'Solbottrend'
    try:
        bot = LiveBot.objects.get(name=bot_name)
        symbol = bot.pair.symbol
        params = bot.parameters
        timeframe = bot.timeframe if hasattr(bot, 'timeframe') else '1h'
        
        print(f"Checking {symbol} on {timeframe} with params {params}")
        
        exchange = ccxt.binance()
        bars = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=100)
        df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        
        strategy = DayTradingStrategy(parameters=params)
        df_signals = strategy.generate_signals(df)
        
        print("\n--- Last 10 Signal Rows ---")
        print(df_signals[['timestamp', 'close', 'ema9', 'ema21', 'adx', 'rsi', 'strength', 'signal']].tail(10))
        
        last_row = df_signals.iloc[-1]
        print(f"\n--- Current Stats for {symbol} ---")
        print(f"Price: {last_row['close']}")
        print(f"ADX: {last_row['adx']:.2f} (Required: {params.get('min_adx')})")
        print(f"Strength: {last_row['strength']:.2f} (Required: {params.get('min_strength')})")
        print(f"RSI: {last_row['rsi']:.2f}")
        print(f"EMA9: {last_row['ema9']:.2f}")
        print(f"EMA21: {last_row['ema21']:.2f}")
        print(f"MACD > Signal: {last_row['macd'] > last_row['signal_macd']}")
        print(f"Signal: {last_row['signal']}")
        
        # Check why it might not be buying
        reasons = []
        if not (last_row['ema9'] > last_row['ema21']): reasons.append("EMA Crossover not bullish (EMA9 <= EMA21)")
        if not (last_row['close'] > last_row['ema50']): reasons.append("Price below EMA50")
        if not (last_row['close'] > last_row['ema200']): reasons.append("Price below EMA200")
        if not (last_row['macd'] > last_row['signal_macd']): reasons.append("MACD below Signal")
        if not (last_row['rsi'] > float(params.get('rsi_buy', 55))): reasons.append(f"RSI too low ({last_row['rsi']:.2f} <= 55)")
        if not (last_row['adx'] >= float(params.get('min_adx', 0))): reasons.append(f"ADX too low ({last_row['adx']:.2f} < {params.get('min_adx')})")
        if not (last_row['strength'] >= float(params.get('min_strength', 0))): reasons.append(f"Strength too low ({last_row['strength']:.2f} < {params.get('min_strength')})")
        
        if reasons:
            print("\nConditions NOT met because:")
            for r in reasons:
                print(f"  - {r}")
        else:
            print("\nConditions ARE met! A signal should be generated.")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    diagnostic()
