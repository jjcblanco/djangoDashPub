#!/usr/bin/env python3
"""
Adjust day trading bot parameters for better signal generation.
"""
import os
import sys
import django

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')
django.setup()

from dashboard.models import LiveBot

def adjust_parameters():
    """Adjust parameters for all day trading bots."""
    day_bots = LiveBot.objects.filter(strategy_type='DAYTRADING')
    print(f'Found {day_bots.count()} day trading bots')
    
    for bot in day_bots:
        print(f'\nBot {bot.id}: {bot.name} (status: {bot.status})')
        params = bot.parameters
        
        # Enable dynamic RSI thresholds
        params['rsi_upper_dynamic'] = True
        params['rsi_lower_dynamic'] = True
        
        # Set min_adx to 20 (default) if currently higher than 25
        if params.get('min_adx', 20) > 25:
            params['min_adx'] = 20
        
        # Ensure volume filter is on
        params['use_volume_filter'] = True
        
        # Set market regime filter to True
        params['market_regime_filter'] = True
        
        # Reduce cooldown bars to 3 (if higher)
        if params.get('cooldown_bars', 5) > 5:
            params['cooldown_bars'] = 5
        
        # Risk per trade conservative
        params['risk_per_trade_pct'] = min(params.get('risk_per_trade_pct', 2.0), 2.0)
        
        # Update bot
        bot.parameters = params
        bot.save()
        
        print(f'  Updated parameters:')
        print(f'    rsi_upper_dynamic: {params["rsi_upper_dynamic"]}')
        print(f'    rsi_lower_dynamic: {params["rsi_lower_dynamic"]}')
        print(f'    min_adx: {params.get("min_adx")}')
        print(f'    cooldown_bars: {params.get("cooldown_bars")}')
    
    print('\nParameters adjusted successfully')

def activate_bots():
    """Activate all PAUSED day trading bots."""
    paused_bots = LiveBot.objects.filter(strategy_type='DAYTRADING', status='PAUSED')
    print(f'\nActivating {paused_bots.count()} PAUSED bots')
    
    for bot in paused_bots:
        bot.status = 'RUNNING'
        bot.save()
        print(f'  Bot {bot.id}: {bot.name} -> RUNNING')
    
    print('Bots activated')

if __name__ == '__main__':
    adjust_parameters()
    activate_bots()
    
    # Final summary
    print('\n' + '='*60)
    print('SUMMARY')
    print('='*60)
    day_bots = LiveBot.objects.filter(strategy_type='DAYTRADING')
    for bot in day_bots:
        print(f'Bot {bot.id}: {bot.name} - {bot.status}')
        print(f'  Params: min_adx={bot.parameters.get("min_adx")}, rsi_dynamic={bot.parameters.get("rsi_upper_dynamic")}')
    print('\nAll day trading bots are now RUNNING with optimized strategy.')