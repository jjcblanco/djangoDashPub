import os
import sys
import traceback

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.criptodash.settings')

import django
django.setup()

from dashboard.models import LiveBot
from dashboard.bot_manager import BotManager

# Get first ERROR bot
error_bot = LiveBot.objects.filter(status='ERROR').first()
if error_bot:
    print(f"Testing bot {error_bot.id}: {error_bot.name}")
    print(f"Pair: {error_bot.pair.symbol}, Strategy: {error_bot.strategy_type}")
    print(f"Is live: {error_bot.is_live}")
    
    # Try to update the bot
    try:
        # First, reset status to RUNNING temporarily
        error_bot.status = 'RUNNING'
        error_bot.save()
        
        # Call update_bot directly
        result = BotManager.update_bot(error_bot)
        print(f"Result: {result}")
        
        # Reset status back to ERROR if still error
        error_bot.refresh_from_db()
        if error_bot.status == 'ERROR':
            print(f"Bot is still in ERROR state")
    except Exception as e:
        print(f"Exception during update: {e}")
        traceback.print_exc()
else:
    print("No ERROR bots found")