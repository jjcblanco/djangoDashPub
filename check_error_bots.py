import os
import django
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.criptodash.settings')
django.setup()

from dashboard.models import LiveBot

error_bots = LiveBot.objects.filter(status='ERROR')
print(f'Found {error_bots.count()} bots in ERROR state')

for bot in error_bots:
    print(f'Bot {bot.id}: {bot.name} ({bot.pair.symbol}) - {bot.strategy_type}')
    print(f'  Last error: {bot.last_error}')
    print(f'  Initial balance: {bot.initial_balance}, Current: {bot.current_balance}')
    print(f'  Is live: {bot.is_live}')
    print()