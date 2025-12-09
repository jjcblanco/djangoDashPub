"""
Test script for backtesting functionality
Run this from Django shell: python manage.py shell < test_backtest.py
"""

import os
import django
import sys

# Add the project directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')
django.setup()

from dashboard.models import TradeSignal, TradingPair, Exchange
from dashboard.backtester import Backtester, SignalBasedStrategy
from django.utils import timezone
from datetime import datetime, timedelta

def test_backtest():
    """Test the backtesting functionality"""
    
    print("=" * 60)
    print("BACKTESTING SYSTEM TEST")
    print("=" * 60)
    
    # 1. Check for signals in database
    print("\n1. Checking for signals in database...")
    total_signals = TradeSignal.objects.count()
    print(f"   Total signals in database: {total_signals}")
    
    if total_signals == 0:
        print("   ⚠️  No signals found. Please run the bot first to generate signals.")
        return
    
    # 2. Get available pairs
    print("\n2. Available trading pairs:")
    pairs = TradingPair.objects.all()
    for pair in pairs:
        signal_count = TradeSignal.objects.filter(pair=pair).count()
        print(f"   - {pair.symbol}: {signal_count} signals")
    
    if not pairs.exists():
        print("   ⚠️  No trading pairs found.")
        return
    
    # 3. Select a pair with signals
    pair_with_signals = None
    for pair in pairs:
        if TradeSignal.objects.filter(pair=pair).exists():
            pair_with_signals = pair
            break
    
    if not pair_with_signals:
        print("   ⚠️  No pairs with signals found.")
        return
    
    print(f"\n3. Testing with pair: {pair_with_signals.symbol}")
    
    # 4. Get date range for signals
    signals = TradeSignal.objects.filter(pair=pair_with_signals).order_by('timestamp')
    first_signal = signals.first()
    last_signal = signals.last()
    
    if not first_signal or not last_signal:
        print("   ⚠️  Could not determine date range.")
        return
    
    start_date = first_signal.timestamp
    end_date = last_signal.timestamp
    
    print(f"   Date range: {start_date.date()} to {end_date.date()}")
    print(f"   Total signals in range: {signals.count()}")
    
    # 5. Run backtest
    print("\n4. Running backtest...")
    print("   Initial balance: $10,000")
    print("   Commission: 0.1%")
    
    try:
        backtester = Backtester(initial_balance=10000, commission=0.001)
        results = backtester.run_backtest_from_signals(
            pair_symbol=pair_with_signals.symbol,
            start_date=start_date,
            end_date=end_date,
            signals_queryset=signals
        )
        
        # 6. Display results
        print("\n5. BACKTEST RESULTS")
        print("   " + "=" * 56)
        
        if 'error' in results:
            print(f"   ❌ Error: {results['error']}")
            return
        
        print(f"   Final Balance:     ${results['final_balance']:,.2f}")
        print(f"   Total Return:      {results['total_return']:.2f}%")
        print(f"   Total Trades:      {results['total_trades']}")
        print(f"   Win Rate:          {results.get('win_rate', 0):.2f}%")
        print(f"   Sharpe Ratio:      {results.get('sharpe_ratio', 0):.2f}")
        print(f"   Max Drawdown:      {results.get('max_drawdown', 0):.2f}%")
        print(f"   Profit Factor:     {results.get('profit_factor', 0):.2f}")
        print(f"   Avg Trade:         {results.get('avg_trade', 0):.2f}%")
        print(f"   Best Trade:        {results.get('best_trade', 0):.2f}%")
        print(f"   Worst Trade:       {results.get('worst_trade', 0):.2f}%")
        print(f"   Total Fees:        ${results.get('total_fees', 0):.2f}")
        
        # 7. Show sample trades
        trades = results.get('trades', [])
        if trades:
            print(f"\n6. Sample Trades (first 5):")
            print("   " + "-" * 56)
            for i, trade in enumerate(trades[:5]):
                action = trade['action']
                price = trade['price']
                timestamp = trade['timestamp']
                print(f"   {i+1}. {action:4s} @ ${price:.4f} on {timestamp}")
        
        print("\n" + "=" * 60)
        print("✅ Backtest completed successfully!")
        print("=" * 60)
        
        # 8. Check if results were saved
        from dashboard.models import BacktestResult
        saved_results = BacktestResult.objects.filter(
            pair=pair_with_signals,
            start_date=start_date,
            end_date=end_date
        ).order_by('-created_at').first()
        
        if saved_results:
            print(f"\n✅ Results saved to database (ID: {saved_results.id})")
        
    except Exception as e:
        print(f"\n❌ Error running backtest: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    test_backtest()
