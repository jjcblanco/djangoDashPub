import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')
django.setup()

from dashboard.models import LiveBot

bot = LiveBot.objects.get(id=3)
print(f"Bot: {bot.name} (ID: {bot.id})")
print(f"Status: {bot.status}")
print(f"Last Error: {bot.last_error}")
print(f"Parameters: {bot.parameters}")

# Check if amount_per_level is present and not None
amount = bot.parameters.get('amount_per_level')
print(f"amount_per_level: '{amount}' (Type: {type(amount)})")
