import os
import django
import sys
import pandas as pd
from decimal import Decimal

# Configuración de Django
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)

# Carga manual de .env
env_path = os.path.join(BASE_DIR, '.env')
if os.path.exists(env_path):
    with open(env_path, 'r') as f:
        for line in f:
            line = line.strip()
            if '=' in line and not line.startswith('#'):
                key, value = line.split('=', 1)
                os.environ[key.strip()] = value.strip().strip("'").strip('"')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')
django.setup()

from dashboard.models import LiveBot, LiveTrade
from dashboard.bot_manager import BotManager

def debug_all_bots():
    print("🔍 AUDITORÍA DE TRADES TRABADOS")
    print("========================================")
    bots = LiveBot.objects.filter(status__in=['RUNNING', 'CLOSE_ONLY'])
    
    for bot in bots:
        print(f"\n--- BOT: {bot.name} (ID: {bot.id}) | Par: {bot.pair.symbol} ---")
        
        # Obtener precio actual
        df = BotManager._get_live_df(bot.pair.symbol, timeframe=bot.parameters.get('timeframe', '1h'))
        if df is None or df.empty:
            print(f"  ❌ Error: No hay datos para {bot.pair.symbol}")
            continue
            
        current_price = float(df['close'].iloc[-1])
        print(f"  Precio Actual: {current_price}")
        
        # Calcular grid_step para bots GRID
        grid_step = 0
        if bot.strategy_type == 'GRID':
            try:
                upper = float(bot.parameters.get('upper_price'))
                lower = float(bot.parameters.get('lower_price'))
                levels = int(bot.parameters.get('grid_levels'))
                grid_step = (upper - lower) / (levels - 1)
                print(f"  Paso Grid: {grid_step:.4f}")
            except:
                print("  ⚠️ Error calculando paso grid.")

        # Buscar trades abiertos
        open_trades = LiveTrade.objects.filter(bot=bot, status__in=['OPEN', 'WAITING'])
        print(f"  Trades Pendientes: {open_trades.count()}")
        
        for t in open_trades:
            if t.status == 'WAITING':
                diff = current_price - float(t.entry_price)
                print(f"    - [WAIT BUY] ID: {t.id} | Entrada: {t.entry_price} | Dif: {diff:+.4f}")
            else: # OPEN (Wait Sell)
                target_tp = float(t.entry_price) + grid_step
                diff_to_tp = target_tp - current_price
                print(f"    - [WAIT SELL] ID: {t.id} | Entrada: {t.entry_price} | TP Target: {target_tp:.4f} | Dist. a TP: {diff_to_tp:.4f}")
                
                if current_price >= target_tp:
                    print(f"      🚨 BUG DETECTADO: El precio {current_price} ya superó el TP {target_tp:.4f} pero el trade sigue OPEN.")

if __name__ == "__main__":
    debug_all_bots()
