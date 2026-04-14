#!/usr/bin/env python3
"""
Test parameter migration for optimized strategy.
"""
import os
import sys
import django

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')
django.setup()

from dashboard.models import LiveBot
from dashboard.bot_manager import BotManager

# Test with each day trading bot
day_bots = LiveBot.objects.filter(strategy_type='DAYTRADING')
for b in day_bots:
    print(f'\nBot {b.id}: {b.name}')
    print('Original params:', b.parameters)
    
    # Simulate migration
    migrated = BotManager._migrate_to_optimized_params(b.parameters)
    print('Migrated params:', migrated)
    
    # Check for required keys
    required = ['ema_fast', 'ema_slow', 'ema_trend', 'rsi_period', 
                'atr_sl_multiplier', 'atr_tp_multiplier', 'min_adx']
    missing = [k for k in required if k not in migrated]
    if missing:
        print('WARNING: Missing keys:', missing)
    else:
        print('All required keys present')