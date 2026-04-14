#!/usr/bin/env python3
"""
Migrate day trading bots to use optimized strategy.
"""
import os
import sys
import django

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')
django.setup()

from dashboard.models import LiveBot
from dashboard.bot_manager import BotManager

def migrate_bots():
    """Migrate all day trading bots to optimized strategy."""
    day_bots = LiveBot.objects.filter(strategy_type='DAYTRADING')
    print(f'Found {day_bots.count()} day trading bots')
    
    updated_count = 0
    for bot in day_bots:
        print(f'\nBot {bot.id}: {bot.name} (status: {bot.status})')
        
        # Pause RUNNING bots temporarily
        if bot.status == 'RUNNING':
            print(f'  -> Pausing RUNNING bot for migration')
            bot.status = 'PAUSED'
            bot.save()
        
        # Migrate parameters
        original_params = bot.parameters
        migrated_params = BotManager._migrate_to_optimized_params(original_params)
        
        # Ensure use_optimized_strategy is True
        migrated_params['use_optimized_strategy'] = True
        
        # Update bot parameters
        bot.parameters = migrated_params
        bot.save()
        
        print(f'  Parameters migrated: {len(original_params)} -> {len(migrated_params)}')
        print(f'  New keys: {list(migrated_params.keys())}')
        updated_count += 1
    
    print(f'\n✅ Migrated {updated_count} bots')
    
    # List updated bots
    print('\nUpdated bots:')
    for bot in LiveBot.objects.filter(strategy_type='DAYTRADING'):
        print(f'  {bot.id}: {bot.name} - {bot.status}')

if __name__ == '__main__':
    migrate_bots()