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

def force_bootstrap_solbot():
    try:
        bot = LiveBot.objects.get(id=3)
        print(f"🚀 INICIANDO REINICIO FORZADO: {bot.name} (ID: {bot.id})")
        
        # 1. Limpiar trades "zombie"
        old_trades = LiveTrade.objects.filter(bot=bot).exclude(status__in=['CLOSED', 'CANCELED', 'CLOSED_EMERGENCY'])
        count = old_trades.count()
        old_trades.update(status='CANCELED')
        print(f"  ✅ {count} trades antiguos cancelados.")

        # 2. Restaurar balance (opcional, para empezar limpio)
        if bot.current_balance != bot.initial_balance:
            bot.current_balance = bot.initial_balance
            bot.save()
            print(f"  ✅ Balance restaurado a {bot.initial_balance} USDT.")

        # 3. Disparar Bootstrap
        params = bot.parameters
        upper = float(params.get('upper_price'))
        lower = float(params.get('lower_price'))
        levels_count = int(params.get('grid_levels'))
        
        grid_step = (upper - lower) / (levels_count - 1)
        grid_levels = [lower + i * grid_step for i in range(levels_count)]
        
        # Obtener precio actual para pasar al bootstrap
        df = BotManager._get_live_df(bot.pair.symbol)
        if df is None or df.empty:
            print("❌ No se pudo obtener el precio para el bootstrap.")
            return
        
        current_price = float(df['close'].iloc[-1])
        print(f"  Precio actual: {current_price}. Ejecutando Bootstrap...")
        
        # Ejecutar bootstrap real
        result = BotManager._grid_bootstrap(bot, current_price, grid_levels)
        print(f"  ✅ Bootstrap completado: {result}")

    except Exception as e:
        import traceback
        print(f"❌ Error durante el reinicio: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    force_bootstrap_solbot()
