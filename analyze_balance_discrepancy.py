"""
Analyze balance discrepancy between bot records and Binance.
"""
import os
import sys
import django

# Setup Django
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'criptodash'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')
try:
    django.setup()
except:
    pass

from dashboard.models import LiveBot, LiveTrade
from dashboard.ccxttest1 import binance
from decimal import Decimal

def analyze_balances():
    print("=== Balance Discrepancy Analysis ===\n")
    
    # 1. Calculate total balance from bots
    total_bot_balance = Decimal('0')
    total_initial_balance = Decimal('0')
    
    bots = LiveBot.objects.all()
    print(f"Total bots: {bots.count()}")
    print("\nBot balances:")
    for bot in bots:
        total_bot_balance += bot.current_balance
        total_initial_balance += bot.initial_balance
        print(f"  {bot.name:20} (ID: {bot.id:2}) | Current: ${bot.current_balance:12.8f} | Initial: ${bot.initial_balance:12.8f} | Status: {bot.status}")
    
    print(f"\nTotal across all bots:")
    print(f"  Current balance: ${total_bot_balance:.8f}")
    print(f"  Initial balance: ${total_initial_balance:.8f}")
    print(f"  Total PnL (current - initial): ${total_bot_balance - total_initial_balance:.8f}")
    
    # 2. Check Binance balance (only for live bots)
    live_bots = LiveBot.objects.filter(is_live=True)
    print(f"\nLive bots (connected to Binance): {live_bots.count()}")
    
    total_live_balance = Decimal('0')
    for bot in live_bots:
        total_live_balance += bot.current_balance
    
    print(f"Total live bot balance: ${total_live_balance:.8f}")
    
    # 3. Fetch actual Binance balance
    print("\nFetching Binance balance...")
    try:
        balance = binance.fetch_balance()
        usdt_balance = Decimal(str(balance['USDT']['free']))
        usdt_total = Decimal(str(balance['USDT']['total']))
        usdt_used = usdt_total - usdt_balance
        
        print(f"Binance USDT balance:")
        print(f"  Free:  ${usdt_balance:.8f}")
        print(f"  Total: ${usdt_total:.8f}")
        print(f"  Used:  ${usdt_used:.8f}")
        
        # 4. Calculate discrepancy
        discrepancy = total_live_balance - usdt_total
        print(f"\nDiscrepancy (Bot Total - Binance Total): ${discrepancy:.8f}")
        
        if abs(discrepancy) > Decimal('0.01'):
            print(f"⚠️  SIGNIFICANT DISCREPANCY DETECTED: ${discrepancy:.2f}")
            
            # 5. Analyze potential causes
            print("\nPotential causes:")
            print("  1. Open trades not accounted for in bot.current_balance")
            print("  2. Commission/fee discrepancies")
            print("  3. Binance balance includes other assets not tracked")
            print("  4. Timing differences (orders pending execution)")
            
            # Check open trades
            open_trades = LiveTrade.objects.filter(status='OPEN')
            print(f"\nOpen trades: {open_trades.count()}")
            open_trade_value = Decimal('0')
            for trade in open_trades:
                if trade.bot.is_live:
                    # Approximate value at entry price
                    value = trade.entry_price * trade.amount
                    open_trade_value += value
                    print(f"  Bot {trade.bot.id}: {trade.amount:.8f} {trade.bot.pair.symbol} @ ${trade.entry_price:.8f} = ${value:.8f}")
            
            print(f"Total open trade value: ${open_trade_value:.8f}")
            
            # Adjusted discrepancy
            adjusted_discrepancy = total_live_balance - (usdt_total + open_trade_value)
            print(f"\nAdjusted discrepancy (after open trades): ${adjusted_discrepancy:.8f}")
            
        else:
            print("✓ Balance discrepancy within acceptable margin (< $0.01)")
            
    except Exception as e:
        print(f"Error fetching Binance balance: {e}")
        import traceback
        traceback.print_exc()
    
    # 6. Check for negative balances (should not happen)
    negative_bots = LiveBot.objects.filter(current_balance__lt=0)
    if negative_bots.exists():
        print(f"\n⚠️  WARNING: {negative_bots.count()} bots have negative balance!")
        for bot in negative_bots:
            print(f"  Bot {bot.id}: {bot.name} = ${bot.current_balance:.8f}")

if __name__ == '__main__':
    analyze_balances()