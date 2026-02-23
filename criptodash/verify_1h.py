import os
import django
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from django.utils import timezone

# Initialize Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')
django.setup()

from dashboard.models import TradingPair, OHLCVData, TradeSignal
from dashboard.backtester import Backtester
from dashboard.ccxttest1 import binance, signals as generate_signals, save_signals_to_db

def run_verification():
    symbol = 'BNB/USDT'
    timeframe = '1h'
    days_back = 60
    
    print(f"--- Verifying Strategy for {symbol} on {timeframe} ---")
    
    # 1. Get or Create Pair
    pair, created = TradingPair.objects.get_or_create(
        symbol=symbol,
        defaults={'base_asset': 'BNB', 'quote_asset': 'USDT', 'exchange_id': 1} # Assuming default exchange
    )
    
    # 2. Fetch Data from Binance
    print(f"Fetching {timeframe} data for the last {days_back} days...")
    since = binance.parse8601((datetime.now() - timedelta(days=days_back)).isoformat())
    ohlcv = binance.fetch_ohlcv(symbol, timeframe, since=since)
    
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    
    # 3. Save OHLCV to DB (required for backtester chart)
    print("Saving OHLCV data to database...")
    for _, row in df.iterrows():
        OHLCVData.objects.update_or_create(
            pair=pair,
            timestamp=timezone.make_aware(row['timestamp']),
            timeframe=timeframe,
            defaults={
                'open': row['open'],
                'high': row['high'],
                'low': row['low'],
                'close': row['close'],
                'volume': row['volume']
            }
        )
    
    # 4. Generate Signals with new Scoring System
    print("Generating signals with confluence scoring...")
    # Clean old signals for this test period to avoid confusion
    TradeSignal.objects.filter(pair=pair, timestamp__gte=timezone.make_aware(df['timestamp'].min())).delete()
    
    # The signals function calculates the scores
    df_with_signals = generate_signals(df.copy())
    
    # Now save them to the DB so the backtester can find them (tagging them as '1h')
    save_signals_to_db(df_with_signals, symbol, timeframe=timeframe)
    
    # 5. Run Backtest
    print("\nRunning Backtest with Advanced Tuning...")
    backtester = Backtester(initial_balance=1000, commission=0.001)
    
    # Parameters for the "Sweet Spot" - Optimizing for 1h
    results = backtester.run_backtest_from_signals(
        pair_symbol=symbol,
        start_date=timezone.make_aware(df['timestamp'].min()),
        end_date=timezone.make_aware(df['timestamp'].max()),
        timeframe=timeframe,   # Filter by the correct timeframe
        min_strength=4,        # Stricter confluence filter
        stop_loss_pct=None,    # Uses signals' SL
        take_profit_pct=None,  # Uses signals' TP
        trailing_stop=True     # Enable Trailing Stop
    )
    
    # 6. Report Results
    if 'error' in results:
        print(f"Error: {results['error']}")
        return

    print("\n" + "="*30)
    print(f"RESULTS FOR {symbol} ({timeframe})")
    print("="*30)
    print(f"Total Return: {results['total_return']:.2f}%")
    print(f"Win Rate: {results['win_rate']:.2f}%")
    print(f"Total Trades: {results['total_trades']}")
    print(f"Max Drawdown: {results['max_drawdown']:.2f}%")
    print(f"Profit Factor: {results['profit_factor']:.2f}")
    print("="*30)
    
    # 7. Print Trade Log for analysis
    print("\nTRADE LOG:")
    trades = results.get('trades', [])
    for i, trade in enumerate(trades):
        if trade['action'] == 'SELL':
            # Find corresponding BUY (simplified logic for this script)
            buy = trades[max(0, i-1)] 
            print(f"Trade {i//2 + 1}: {buy['timestamp']} to {trade['timestamp']} | Result: {'WIN' if trade['pnl'] > 0 else 'LOSS'} | Exit: {trade.get('reason')} | PnL: {trade['pnl_pct']:.2f}%")

    if results['win_rate'] > 40:
        print("\n✅ SIGNIFICANT IMPROVEMENT! Win rate is much higher than 20%.")
    else:
        print("\n⚠️ Win rate still low. Consider increasing 'min_strength' to 4 or 5.")

if __name__ == "__main__":
    run_verification()
