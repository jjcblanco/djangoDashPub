#!/usr/bin/env python3
"""
List all bots and their status.
"""
import os
import sys
import django

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')
django.setup()

from dashboard.models import LiveBot

bots = LiveBot.objects.all()
print(f'Total bots: {bots.count()}')
print('-'*80)
for b in bots:
    print(f'Bot {b.id}: {b.name} ({b.pair.symbol}) - {b.strategy_type} - {b.status}')
    print(f'  Initial: {b.initial_balance}, Current: {b.current_balance}, Live: {b.is_live}')
    if b.last_error:
        print(f'  Last error: {b.last_error[:100]}')
    print()

day_bots = LiveBot.objects.filter(strategy_type='DAYTRADING')
print(f'\nDay trading bots: {day_bots.count()}')
for b in day_bots:
    print(f'  {b.id}: {b.name} - {b.status}')

grid_bots = LiveBot.objects.filter(strategy_type='GRID')
print(f'\nGrid bots: {grid_bots.count()}')
for b in grid_bots:
    print(f'  {b.id}: {b.name} - {b.status}')