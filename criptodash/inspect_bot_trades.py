import os
import django
import argparse
from decimal import Decimal

# --- CONFIGURACIÓN PARA AMBIENTE VPS/LOCAL ---
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

from dashboard.models import LiveBot, LiveTrade

def inspect_bot(bot_id):
    try:
        bot = LiveBot.objects.get(id=bot_id)
        print(f"\n--- INSPECCIONANDO BOT: {bot.name} (ID: {bot.id}) ---")
        print(f"Estado: {bot.status} | Par: {bot.pair.symbol}")
        print(f"Balance Inicial: {bot.initial_balance} | Actual: {bot.current_balance}")
        print(f"PnL Calculado (Actual - Inicial): {bot.current_balance - bot.initial_balance}")
        
        trades = LiveTrade.objects.filter(bot=bot).order_by('-id')[:20]
        
        print("\nÚltimos 20 Trades:")
        print(f"{'ID':<6} | {'Status':<10} | {'Entry':<10} | {'Exit':<10} | {'PnL':<12}")
        print("-" * 60)
        
        for t in trades:
            pnl_str = f"{t.pnl:.8f}" if t.pnl is not None else "N/A"
            status = t.status
            entry = f"{t.entry_price:.4f}" if t.entry_price else "N/A"
            exit_p = f"{t.exit_price:.4f}" if t.exit_price else "N/A"
            print(f"{t.id:<6} | {status:<10} | {entry:<10} | {exit_p:<10} | {pnl_str:<12}")
            
    except LiveBot.DoesNotExist:
        print(f"Error: No se encontró el bot con ID {bot_id}")
    except Exception as e:
        print(f"Error inesperado: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Inspeccionar trades de un LiveBot")
    parser.add_argument("--bot_id", type=int, required=True, help="ID del bot")
    args = parser.parse_args()
    inspect_bot(args.bot_id)
