#!/usr/bin/env python3
"""
Restore bot cash balances to approximate correct values.
"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'criptodash'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')

import django
django.setup()

from dashboard.models import LiveBot, LiveTrade
from dashboard.ccxttest1 import binance
from decimal import Decimal

def restore_from_initial():
    """Restore bot cash to initial minus open trade costs."""
    print("Restoring bot cash balances...")
    
    live_bots = LiveBot.objects.filter(is_live=True)
    
    for bot in live_bots:
        # Calculate total cost of open trades for this bot
        open_trades = LiveTrade.objects.filter(bot=bot, status='OPEN')
        open_cost = Decimal('0')
        for trade in open_trades:
            # Cost at entry price (amount * entry_price)
            cost = trade.entry_price * trade.amount
            open_cost += cost
        
        # Estimated cash = initial - open cost
        estimated_cash = bot.initial_balance - open_cost
        
        # Ensure non-negative
        if estimated_cash < Decimal('0'):
            estimated_cash = Decimal('0')
        
        print(f"Bot {bot.id} ({bot.name}):")
        print(f"  Initial: ${bot.initial_balance:.8f}")
        print(f"  Open trade cost: ${open_cost:.8f}")
        print(f"  Estimated cash: ${estimated_cash:.8f}")
        print(f"  Previous cash: ${bot.current_balance:.8f}")
        
        # Update
        bot.current_balance = estimated_cash
        bot.save()
    
    # Verify
    total_cash = sum(b.current_balance for b in live_bots)
    print(f"\nTotal restored cash: ${total_cash:.8f}")
    
    # Compare with Binance total
    try:
        balance = binance.fetch_balance()
        usdt_total = Decimal(str(balance['USDT']['total']))
        print(f"Binance total USDT: ${usdt_total:.8f}")
        discrepancy = total_cash - usdt_total
        print(f"Discrepancy after restoration: ${discrepancy:.8f}")
    except Exception as e:
        print(f"Error fetching Binance: {e}")

def conservative_restore():
    """Conservative restoration: set cash to Binance free USDT distributed proportionally."""
    print("\nConservative restoration...")
    
    try:
        balance = binance.fetch_balance()
        usdt_free = Decimal(str(balance['USDT']['free']))
        usdt_total = Decimal(str(balance['USDT']['total']))
        print(f"Binance free USDT: ${usdt_free:.8f}")
        print(f"Binance total USDT: ${usdt_total:.8f}")
        
        live_bots = LiveBot.objects.filter(is_live=True)
        
        # Distribute free USDT proportionally to initial balances
        total_initial = sum(b.initial_balance for b in live_bots)
        if total_initial > 0:
            for bot in live_bots:
                share = bot.initial_balance / total_initial
                new_cash = usdt_free * share
                bot.current_balance = new_cash
                bot.save()
                print(f"Bot {bot.id}: ${new_cash:.8f}")
            
            total_cash = sum(b.current_balance for b in live_bots)
            print(f"Total cash set to free USDT: ${total_cash:.8f}")
        else:
            print("Total initial balance is zero.")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    print("=== RESTORE BOT CASH BALANCES ===\n")
    
    # Method 1: Restore from initial minus open trades
    restore_from_initial()
    
    # Method 2: Conservative approach
    # conservative_restore()
    
    print("\nDone.")