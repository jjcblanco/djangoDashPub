#!/usr/bin/env python3
"""
Fix balance discrepancy by syncing bot cash with Binance.
"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'criptodash'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')

import django
django.setup()

from dashboard.models import LiveBot, LiveTrade, GlobalSettings
from dashboard.ccxttest1 import binance
from decimal import Decimal, ROUND_DOWN
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fetch_binance_balance():
    """Fetch Binance USDT balance."""
    try:
        balance = binance.fetch_balance()
        usdt_free = Decimal(str(balance['USDT']['free']))
        usdt_total = Decimal(str(balance['USDT']['total']))
        usdt_used = usdt_total - usdt_free
        return usdt_free, usdt_total, usdt_used
    except Exception as e:
        logger.error(f"Error fetching Binance balance: {e}")
        return None, None, None

def calculate_discrepancy():
    """Calculate discrepancy between bot cash and Binance free USDT."""
    live_bots = LiveBot.objects.filter(is_live=True)
    total_bot_cash = sum(b.current_balance for b in live_bots)
    
    usdt_free, usdt_total, usdt_used = fetch_binance_balance()
    if usdt_free is None:
        return None, None, None, None
    
    discrepancy_cash = total_bot_cash - usdt_free
    discrepancy_total = total_bot_cash - usdt_total
    
    return total_bot_cash, usdt_free, usdt_total, discrepancy_cash

def fix_discrepancy():
    """Fix cash discrepancy by adjusting bot balances."""
    print("=== FIXING BALANCE DISCREPANCY ===\n")
    
    total_bot_cash, usdt_free, usdt_total, discrepancy = calculate_discrepancy()
    if discrepancy is None:
        print("Failed to fetch Binance balance.")
        return False
    
    print(f"Total bot cash: ${total_bot_cash:.8f}")
    print(f"Binance free USDT: ${usdt_free:.8f}")
    print(f"Binance total USDT: ${usdt_total:.8f}")
    print(f"Discrepancy (cash - free): ${discrepancy:.8f}")
    
    if abs(discrepancy) < Decimal('0.01'):
        print("\nNo significant discrepancy found.")
        return True
    
    live_bots = LiveBot.objects.filter(is_live=True)
    
    # Option 1: Proportional adjustment
    print(f"\nProposed adjustment: ${-discrepancy:.8f} total")
    
    if total_bot_cash > 0:
        print("\nAdjusting bot balances proportionally:")
        adjustments = []
        for bot in live_bots:
            if bot.current_balance > 0:
                share = bot.current_balance / total_bot_cash
                adjustment = -discrepancy * share
                adjustments.append((bot, adjustment))
        
        # Apply adjustments
        for bot, adjustment in adjustments:
            old_balance = bot.current_balance
            new_balance = old_balance + adjustment
            if new_balance < 0:
                print(f"  Bot {bot.id} ({bot.name}): Would go negative (${new_balance:.8f}), capping at $0.00")
                new_balance = Decimal('0.00')
            
            print(f"  Bot {bot.id} ({bot.name}): ${old_balance:.8f} -> ${new_balance:.8f} (adjustment: ${adjustment:.8f})")
            bot.current_balance = new_balance
            bot.save()
        
        print("\n✅ Bot balances adjusted.")
        
        # Create an adjustment record
        from django.utils import timezone
        LiveTrade.objects.create(
            bot=None,  # Global adjustment
            side='ADJUST',
            entry_price=Decimal('0'),
            exit_price=Decimal('0'),
            amount=Decimal('0'),
            status='CLOSED',
            pnl=discrepancy,
            commission=Decimal('0'),
            entry_time=timezone.now(),
            exit_time=timezone.now(),
            stop_loss=None,
            take_profit=None
        )
        
        # Update global metrics
        try:
            from dashboard.utils.performance import snapshot_daily_metrics
            snapshot_daily_metrics()
            print("Daily metrics updated.")
        except Exception as e:
            print(f"Note: Could not update daily metrics: {e}")
        
        return True
    else:
        print("\nCannot adjust: total bot cash is zero or negative.")
        return False

def audit_trade_statuses():
    """Audit and fix trade statuses."""
    print("\n=== AUDITING TRADE STATUSES ===")
    
    # Check WAITING trades that might be stale
    waiting_trades = LiveTrade.objects.filter(status='WAITING')
    print(f"WAITING trades: {waiting_trades.count()}")
    
    for trade in waiting_trades:
        # Check if order still exists on exchange
        if trade.bot.is_live and trade.order_id:
            try:
                order = binance.fetch_order(trade.order_id, trade.bot.pair.symbol)
                status = order.get('status')
                print(f"  Trade {trade.id}: order {trade.order_id} status = {status}")
                
                if status == 'closed':
                    # Order filled but not updated
                    print(f"    -> Should be OPEN")
                    # Would need to implement full sync logic here
                elif status == 'canceled':
                    print(f"    -> Should be CANCELED")
            except Exception as e:
                print(f"  Trade {trade.id}: error checking order: {e}")
    
    # Check OPEN trades that might be unfilled
    open_trades = LiveTrade.objects.filter(status='OPEN')
    print(f"\nOPEN trades: {open_trades.count()}")
    
    suspicious = []
    for trade in open_trades:
        # If there's no exit_order_id and it's a grid bot, should have TP order
        if trade.bot.strategy_type == 'GRID' and not trade.exit_order_id:
            print(f"  Trade {trade.id}: OPEN GRID trade without exit_order_id")
            suspicious.append(trade)
    
    if suspicious:
        print(f"\nFound {len(suspicious)} suspicious OPEN trades.")
    
    return True

def main():
    """Main reconciliation routine."""
    print("Starting balance discrepancy fix...")
    
    # 1. Fix cash discrepancy
    success = fix_discrepancy()
    
    # 2. Audit trades
    audit_trade_statuses()
    
    # 3. Final check
    if success:
        print("\n=== FINAL CHECK ===")
        total_bot_cash, usdt_free, usdt_total, discrepancy = calculate_discrepancy()
        if discrepancy is not None:
            print(f"Remaining discrepancy: ${discrepancy:.8f}")
            if abs(discrepancy) < Decimal('1.00'):
                print("✅ Discrepancy resolved (within $1 tolerance).")
            else:
                print("⚠️  Significant discrepancy remains. Manual review needed.")
    
    print("\nDone.")

if __name__ == '__main__':
    main()