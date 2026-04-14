#!/usr/bin/env python3
"""
Inspect parameters of day trading bots.
"""
import os
import sys
import django
import json

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')
django.setup()

from dashboard.models import LiveBot

day_bots = LiveBot.objects.filter(strategy_type='DAYTRADING')
for b in day_bots:
    print(f'\nBot {b.id}: {b.name} ({b.status})')
    print(f'Parameters:')
    params = b.parameters
    for k, v in params.items():
        print(f'  {k}: {v} ({type(v).__name__})')