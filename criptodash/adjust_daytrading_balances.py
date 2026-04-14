#!/usr/bin/env python3
"""
Adjust day trading bot balances to enable trading.
"""
import os
import sys
import django

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')
django.setup()

from dashboard.models import LiveBot

def main():
    # Update day trading bots
    day_bots = LiveBot.objects.filter(strategy_type='DAYTRADING', status='RUNNING')
    print(f"Found {day_bots.count()} day trading bots")
    
    new_balance = 50.0  # USDT
    
    for bot in day_bots:
        print(f"Bot {bot.id}: {bot.name} - Current balance: {bot.current_balance}, Initial: {bot.initial_balance}")
        
        # Update both initial and current balance
        bot.initial_balance = new_balance
        bot.current_balance = new_balance
        bot.save()
        
        print(f"  Updated to {new_balance} USDT")
    
    print("\nBalances updated successfully.")

if __name__ == '__main__':
    main()