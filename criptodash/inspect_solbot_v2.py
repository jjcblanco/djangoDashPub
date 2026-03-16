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

def inspect_solbot():
    try:
        bot = LiveBot.objects.get(id=3)
        print(f"🔍 INSPECCIÓN DETALLADA: {bot.name} (ID: {bot.id})")
        print(f"========================================")
        print(f"Estado: {bot.status} | Saldo: {bot.current_balance}")
        print(f"Parámetros: {bot.parameters}")
        
        df = BotManager._get_live_df(bot.pair.symbol)
        if df is not None and not df.empty:
            price = float(df['close'].iloc[-1])
            print(f"Precio Actual: {price}")
        else:
            print("❌ No se pudo obtener el precio.")
            return

        trades = LiveTrade.objects.filter(bot=bot).exclude(status__in=['CLOSED', 'CANCELED', 'CLOSED_EMERGENCY'])
        print(f"Trades Activos en BD: {trades.count()}")
        
        for t in trades:
            print(f"  - ID: {t.id} | Status: {t.status} | Lado: {t.side} | Entrada: {t.entry_price}")

        if trades.count() == 0:
            print("\n💡 EL BOT NO TIENE ÓRDENES ACTIVAS.")
            print("Esto significa que el Bootstrap no ha ocurrido o falló.")
            
            # Verificar si run_bots está realmente procesando este bot
            print("\nIntentando simular un ciclo de actualización para detectar errores...")
            try:
                res = BotManager.update_bot(bot)
                print(f"Resultado de update_bot: {res}")
            except Exception as e:
                print(f"❌ Error al ejecutar update_bot: {e}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    inspect_solbot()
