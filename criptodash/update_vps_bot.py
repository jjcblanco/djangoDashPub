import os
import django
import argparse
import json
from decimal import Decimal

# --- CONFIGURACIÓN PARA AMBIENTE VPS/LOCAL ---
# Intentar cargar .env del VPS si existe
env_file = "/var/www/javierblanco.com.ar/web/criptodash/.env"
if os.path.exists(env_file):
    with open(env_file, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"): continue
            if "=" in line:
                key, val = line.split("=", 1)
                os.environ[key.strip()] = val.strip().strip("'").strip('"')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')
django.setup()

from dashboard.models import LiveBot

def update_bot(bot_id, mode=None, custom_params=None, new_balance=None):
    try:
        bot = LiveBot.objects.get(id=bot_id)
        print(f"Bot encontrado: {bot.name} (ID: {bot.id})")
        
        # 1. Actualizar Balance si se solicita
        if new_balance is not None:
            old_val = bot.current_balance
            bot.current_balance = Decimal(str(new_balance))
            print(f"Actualizando BALANCE: {old_val} -> {bot.current_balance}")
        
        # 2. Actualizar Parámetros
        params = bot.parameters.copy()
        
        if mode == 'balanced':
            print("Aplicando modo BALANCED...")
            params.update({
                "strategy_mode": "balanced",
                "allow_late_entry": True,
                "use_candles": True,
                "use_bollinger_filter": True,
                "min_strength": 4.0,
                "min_adx": 20.0,
                "atr_sl": 1.5,
                "atr_tp": 3.0
            })
        elif mode == 'conservative':
            print("Aplicando modo CONSERVATIVE...")
            params.update({
                "strategy_mode": "conservative",
                "allow_late_entry": False,
                "use_candles": True,
                "use_bollinger_filter": True,
                "min_strength": 6.0,
                "min_adx": 25.0,
                "atr_sl": 2.0,
                "atr_tp": 4.0
            })
            
        if custom_params:
            try:
                extra = json.loads(custom_params)
                params.update(extra)
            except Exception as e:
                print(f"Error parseando custom_params: {e}")
                return

        bot.parameters = params
        bot.save()
        print(f"¡Éxito! Bot guardado correctamente.")
        print(f"Estado Final - Balance: {bot.current_balance} | Params: {bot.parameters}")
        
    except LiveBot.DoesNotExist:
        print(f"Error: No se encontró el bot con ID {bot_id}")
    except Exception as e:
        print(f"Error inesperado: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Actualizar parámetros de un LiveBot")
    parser.add_argument("--bot_id", type=int, required=True, help="ID del bot en la base de datos")
    parser.add_argument("--mode", type=str, choices=['balanced', 'conservative', 'aggressive'], help="Modo predefinido")
    parser.add_argument("--params", type=str, help="JSON string con parámetros personalizados")
    parser.add_argument("--balance", type=float, help="Nuevo balance actual para el bot")
    
    args = parser.parse_args()
    update_bot(args.bot_id, args.mode, args.params, args.balance)
