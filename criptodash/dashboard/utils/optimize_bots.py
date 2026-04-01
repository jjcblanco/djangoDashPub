import os
import django
import sys
import json
from decimal import Decimal

# Configurar entorno Django
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')
django.setup()

from dashboard.models import LiveBot

def optimize_bot_parameters():
    print("--- ⚙️ Iniciando Optimización de Parámetros ---")
    
    # 1. etcgrid - ETH/USDT
    try:
        bot_etc = LiveBot.objects.get(name="etcgrid")
        print(f"Optimizing: {bot_etc.name}")
        p = bot_etc.parameters
        p['upper_price'] = '2150'
        p['lower_price'] = '1750'
        p['trailing_down'] = True
        bot_etc.parameters = p
        bot_etc.save()
        print("  - Rango ETH ajustado y Trailing Down activado.")
    except LiveBot.DoesNotExist:
        print("  - Bot 'etcgrid' no encontrado.")

    # 2. all time sol
    try:
        bot_sol = LiveBot.objects.get(name="all time sol")
        print(f"Optimizing: {bot_sol.name}")
        p = bot_sol.parameters
        if "SOL" in bot_sol.pair.symbol:
            p['upper_price'] = '110'
            p['lower_price'] = '80'
            print("  - Rango SOL ajustado a 80-110.")
        else:
            p['upper_price'] = '2200'
            p['lower_price'] = '1800'
            print("  - Rango ETH ajustado a 1800-2200.")
        bot_sol.parameters = p
        bot_sol.save()
    except LiveBot.DoesNotExist:
        print("  - Bot 'all time sol' no encontrado.")

    # 3. ethdaynuevo
    try:
        bot_day = LiveBot.objects.get(name="ethdaynuevo")
        print(f"Optimizing: {bot_day.name}")
        p = bot_day.parameters
        p['atr_sl'] = 2.0
        p['min_strength'] = 2.0
        bot_day.parameters = p
        bot_day.save()
        print("  - ATR Stop Loss y Signal Strength optimizados.")
    except LiveBot.DoesNotExist:
        print("  - Bot 'ethdaynuevo' no encontrado.")

if __name__ == "__main__":
    optimize_bot_parameters()
