#!/usr/bin/env python3
"""
Reconcile bot balances with Binance.
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

def get_current_price(symbol):
    """Get current market price for a symbol."""
    try:
        ticker = binance.fetch_ticker(symbol)
        return Decimal(str(ticker['last']))
    except Exception as e:
        print(f"Error fetching price for {symbol}: {e}")
        return Decimal('0')

def reconcile():
    print("=== BALANCE RECONCILIATION ===\n")
    
    # 1. Fetch Binance balance
    try:
        balance = binance.fetch_balance()
        usdt_total = Decimal(str(balance['USDT']['total']))
        print(f"Binance total USDT: ${usdt_total:.8f}")
        
        # Also check other assets
        print("\nBinance asset breakdown:")
        total_portfolio_value = Decimal('0')
        for asset, info in balance['total'].items():
            if info and info > 0:
                if asset == 'USDT':
                    total_portfolio_value += Decimal(str(info))
                    print(f"  {asset}: {info:.8f} (${info:.8f})")
                else:
                    # Get price for this asset
                    symbol = f"{asset}/USDT"
                    try:
                        price = get_current_price(symbol)
                        value = Decimal(str(info)) * price
                        total_portfolio_value += value
                        print(f"  {asset}: {info:.8f} @ ${price:.8f} = ${value:.8f}")
                    except:
                        # Try alternative symbol format
                        try:
                            symbol = f"{asset}USDT"
                            price = get_current_price(symbol)
                            value = Decimal(str(info)) * price
                            total_portfolio_value += value
                            print(f"  {asset}: {info:.8f} @ ${price:.8f} = ${value:.8f}")
                        except:
                            print(f"  {asset}: {info:.8f} (price unknown)")
    except Exception as e:
        print(f"Error fetching Binance balance: {e}")
        return
    
    # 2. Calculate bot portfolio value
    print("\n=== BOT PORTFOLIO ===")
    bots = LiveBot.objects.filter(is_live=True)
    total_bot_cash = Decimal('0')
    total_bot_positions = Decimal('0')
    
    for bot in bots:
        print(f"\nBot {bot.id}: {bot.name} ({bot.pair.symbol})")
        print(f"  Cash: ${bot.current_balance:.8f}")
        total_bot_cash += bot.current_balance
        
        # Open trades for this bot
        open_trades = LiveTrade.objects.filter(bot=bot, status='OPEN')
        if open_trades.exists():
            bot_position_value = Decimal('0')
            for trade in open_trades:
                # Get current price for this pair
                current_price = get_current_price(bot.pair.symbol)
                current_value = trade.amount * current_price
                entry_value = trade.entry_price * trade.amount
                pnl = current_value - entry_value
                bot_position_value += current_value
                
                print(f"  Position: {trade.amount:.8f} {bot.pair.symbol}")
                print(f"    Entry: ${trade.entry_price:.8f} (${entry_value:.8f})")
                print(f"    Current: ${current_price:.8f} (${current_value:.8f})")
                print(f"    PnL: ${pnl:.8f}")
            
            print(f"  Total position value: ${bot_position_value:.8f}")
            total_bot_positions += bot_position_value
    
    total_bot_portfolio = total_bot_cash + total_bot_positions
    print(f"\n=== SUMMARY ===")
    print(f"Binance total portfolio: ${usdt_total:.8f}")
    print(f"Bot cash: ${total_bot_cash:.8f}")
    print(f"Bot positions (current value): ${total_bot_positions:.8f}")
    print(f"Bot total portfolio: ${total_bot_portfolio:.8f}")
    
    discrepancy = total_bot_portfolio - usdt_total
    print(f"\nDiscrepancy: ${discrepancy:.8f}")
    
    if abs(discrepancy) > Decimal('1.00'):
        print(f"\n⚠️  LARGE DISCREPANCY DETECTED!")
        
        # Suggest reconciliation
        print("\n=== RECONCILIATION ACTIONS ===")
        print("1. Create adjustment trade to align bot cash with reality")
        print(f"   Required adjustment: ${-discrepancy:.8f} ({'add' if discrepancy < 0 else 'subtract'} from bot cash)")
        
        # Distribute adjustment proportionally
        if total_bot_cash > 0:
            print("\n2. Proportional adjustment per bot:")
            for bot in bots:
                if bot.current_balance > 0:
                    adjustment = -discrepancy * (bot.current_balance / total_bot_cash)
                    print(f"   Bot {bot.id} ({bot.name}): ${adjustment:.8f}")
    
    # 3. Check for obvious errors
    print("\n=== ERROR CHECKS ===")
    
    # Check bots with balance > initial but no open trades (phantom profits)
    for bot in bots:
        if bot.current_balance > bot.initial_balance * Decimal('1.5'):  # 50%+ gain
            open_trades = LiveTrade.objects.filter(bot=bot, status='OPEN').count()
            if open_trades == 0:
                print(f"  Bot {bot.id} ({bot.name}) has unusual gain: ${bot.current_balance:.8f} vs initial ${bot.initial_balance:.8f}")
    
    # Check for negative balances
    negative_bots = LiveBot.objects.filter(current_balance__lt=0)
    if negative_bots.exists():
        print(f"  {negative_bots.count()} bots have negative balance!")

if __name__ == '__main__':
    reconcile()