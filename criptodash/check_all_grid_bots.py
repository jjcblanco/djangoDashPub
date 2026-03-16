import os
import django
import sys
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

def check_all_grid_details():
    print("🔍 AUDITORÍA DE NIVELES GRID")
    print("========================================")
    bots = LiveBot.objects.filter(strategy_type='GRID', status='RUNNING')
    
    for bot in bots:
        print(f"\n--- BOT: {bot.name} (ID: {bot.id}) | {bot.pair.symbol} ---")
        df = BotManager._get_live_df(bot.pair.symbol)
        if df is None or df.empty:
            print("  ❌ No hay precio.")
            continue
        current_price = float(df['close'].iloc[-1])
        print(f"  Precio Actual: {current_price}")
        
        params = bot.parameters
        upper = float(params.get('upper_price'))
        lower = float(params.get('lower_price'))
        levels_count = int(params.get('grid_levels'))
        grid_step = (upper - lower) / (levels_count - 1)
        
        print(f"  Rango: {lower} - {upper} | Paso: {grid_step:.4f}")
        
        # Generar niveles teóricos
        theoretical_levels = [lower + i * grid_step for i in range(levels_count)]
        
        # Obtener trades reales
        active_trades = LiveTrade.objects.filter(bot=bot).exclude(status__in=['CLOSED', 'CANCELED', 'CLOSED_EMERGENCY'])
        
        print(f"  Trades en BD: {active_trades.count()}")
        for level in theoretical_levels:
            match = active_trades.filter(entry_price__range=(level*0.999, level*1.001)).first()
            status_desc = "✅ OK" if match else "❌ FALTANTE"
            rel_pos = "ABAJO (Buy)" if level < current_price else "ARRIBA (Sell)"
            
            trade_info = f"[{match.id}] {match.status}" if match else "None"
            print(f"    - Nivel {level:10.4f} | {rel_pos} | {status_desc} | {trade_info}")

        if bot.last_error:
            print(f"  ⚠️ Last Error: {bot.last_error}")

if __name__ == "__main__":
    check_all_grid_details()
