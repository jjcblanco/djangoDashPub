
import os
import sys
import django
import json

# Agregar el directorio del proyecto al path
sys.path.append(r'c:\Users\Javier\Desktop\programacion\djangoDashPub\criptodash')

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')
django.setup()

from dashboard.models import LiveBot, TradingPair

def check_bot():
    try:
        bot = LiveBot.objects.get(name='Solbottrend')
        print(f"Bot: {bot.name}")
        print(f"Status: {bot.status}")
        print(f"Pair: {bot.pair.symbol}")
        print(f"Strategy: {bot.strategy_type}")
        print(f"Parameters: {bot.parameters}")
        print(f"Last Error: {bot.last_error}")
        print(f"Initial Balance: {bot.initial_balance}")
        print(f"Current Balance: {bot.current_balance}")
    except LiveBot.DoesNotExist:
        print("Bot 'Solbottrend' not found.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_bot()
