#!/usr/bin/env python3
"""
Detailed balance discrepancy analysis.
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

def main():
    with open('balance_report.txt', 'w', encoding='utf-8') as f:
        # Redirect output
        import contextlib
        class Tee:
            def __init__(self, *files):
                self.files = files
            def write(self, obj):
                for f in self.files:
                    f.write(obj)
            def flush(self):
                for f in self.files:
                    f.flush()
        
        import sys
        original_stdout = sys.stdout
        sys.stdout = Tee(sys.stdout, f)
        
        try:
            print("=== DETAILED BALANCE DISCREPANCY ANALYSIS ===\n")
            
            # Get all bots
            bots = LiveBot.objects.all()
            live_bots = LiveBot.objects.filter(is_live=True)
            
            # Calculate totals
            total_bot = sum(b.current_balance for b in bots)
            total_live = sum(b.current_balance for b in live_bots)
            print(f'Total bot balance: ${total_bot:.8f}')
            print(f'Total live bot balance: ${total_live:.8f}')
            
            # Get Binance balance
            try:
                balance = binance.fetch_balance()
                usdt_free = Decimal(str(balance['USDT']['free']))
                usdt_total = Decimal(str(balance['USDT']['total']))
                print(f'Binance USDT free: ${usdt_free:.8f}')
                print(f'Binance USDT total: ${usdt_total:.8f}')
                
                discrepancy = total_live - usdt_total
                print(f'\nDISCREPANCY (Bot Total - Binance Total): ${discrepancy:.8f}')
                print(f'DISCREPANCY: ${discrepancy:.2f} USD\n')
                
                # Check open trades
                open_trades = LiveTrade.objects.filter(status='OPEN')
                waiting_trades = LiveTrade.objects.filter(status='WAITING')
                print(f'Open trades: {open_trades.count()}')
                print(f'Waiting trades: {waiting_trades.count()}')
                
                open_value = Decimal(0)
                print('\nOpen trade details:')
                for t in open_trades:
                    if t.bot.is_live:
                        value = t.entry_price * t.amount
                        open_value += value
                        print(f'  Bot {t.bot.id} ({t.bot.name}): {t.amount:.8f} {t.bot.pair.symbol} @ ${t.entry_price:.8f} = ${value:.8f}')
                
                waiting_value = Decimal(0)
                print('\nWaiting trade details:')
                for t in waiting_trades:
                    if t.bot.is_live:
                        value = t.entry_price * t.amount
                        waiting_value += value
                        print(f'  Bot {t.bot.id} ({t.bot.name}): {t.amount:.8f} {t.bot.pair.symbol} @ ${t.entry_price:.8f} = ${value:.8f}')
                
                print(f'\nTotal open trade value: ${open_value:.8f}')
                print(f'Total waiting trade value: ${waiting_value:.8f}')
                
                # Total allocated = bot balance + open value + waiting value
                total_allocated = total_live + open_value + waiting_value
                print(f'\nTotal allocated (bot balance + open + waiting): ${total_allocated:.8f}')
                
                # New discrepancy
                new_discrepancy = total_allocated - usdt_total
                print(f'Discrepancy after accounting for trades: ${new_discrepancy:.8f}')
                
                # List all live bots with details
                print(f'\n=== LIVE BOT DETAILS ===')
                for bot in live_bots:
                    print(f'\nBot {bot.id}: {bot.name}')
                    print(f'  Pair: {bot.pair.symbol}')
                    print(f'  Strategy: {bot.strategy_type}')
                    print(f'  Status: {bot.status}')
                    print(f'  Current balance: ${bot.current_balance:.8f}')
                    print(f'  Initial balance: ${bot.initial_balance:.8f}')
                    print(f'  PnL: ${bot.current_balance - bot.initial_balance:.8f}')
                    
                    # Bot's open trades
                    bot_open = LiveTrade.objects.filter(bot=bot, status='OPEN')
                    bot_waiting = LiveTrade.objects.filter(bot=bot, status='WAITING')
                    if bot_open.exists() or bot_waiting.exists():
                        print(f'  Open trades: {bot_open.count()}')
                        for t in bot_open:
                            print(f'    - {t.side} {t.amount:.8f} @ ${t.entry_price:.8f}')
                        print(f'  Waiting trades: {bot_waiting.count()}')
                        for t in bot_waiting:
                            print(f'    - {t.side} {t.amount:.8f} @ ${t.entry_price:.8f}')
                
                # Analyze the discrepancy
                print(f'\n=== DISCREPANCY ANALYSIS ===')
                print(f'The discrepancy of ${discrepancy:.2f} could be caused by:')
                print('1. Commissions/fees not properly deducted')
                print('2. Timing differences (orders in flight)')
                print('3. Binance balance includes other assets not tracked')
                print('4. Errors in trade closing calculations')
                print('5. Missing trade records')
                
                # Check if any bots have balance > initial (profit) that might explain discrepancy
                profitable_bots = [b for b in live_bots if b.current_balance > b.initial_balance]
                print(f'\nProfitable live bots: {len(profitable_bots)}')
                total_profit = sum(b.current_balance - b.initial_balance for b in profitable_bots)
                print(f'Total profit from these bots: ${total_profit:.8f}')
                
                loss_bots = [b for b in live_bots if b.current_balance < b.initial_balance]
                print(f'\nLosing live bots: {len(loss_bots)}')
                total_loss = sum(b.current_balance - b.initial_balance for b in loss_bots)
                print(f'Total loss from these bots: ${total_loss:.8f}')
                
                # Check commission totals
                all_trades = LiveTrade.objects.all()
                total_commission = sum(t.commission for t in all_trades)
                print(f'\nTotal commission paid (all trades): ${total_commission:.8f}')
                
            except Exception as e:
                print(f'Error: {e}')
                import traceback
                traceback.print_exc()
        
        finally:
            sys.stdout = original_stdout
    
    print("\nReport written to balance_report.txt")

if __name__ == '__main__':
    main()