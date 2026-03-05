import os
import django
import sys

# Setup Django
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')
django.setup()

from dashboard.models import LiveBot, LiveTrade
from dashboard.ccxttest1 import binance as exchange
from decimal import Decimal

def audit_balances():
    print("--- Auditoría de Balances ---")
    
    # 1. Obtener balance real de Binance
    try:
        bal = exchange.fetch_balance()
        real_free = Decimal(str(bal['free'].get('USDT', 0)))
        real_used = Decimal(str(bal['used'].get('USDT', 0)))
        real_total = Decimal(str(bal['total'].get('USDT', 0)))
        print(f"Binance REAL USDT:")
        print(f"  Total: {real_total}")
        print(f"  Libre: {real_free}")
        print(f"  Usado (en órdenes): {real_used}")
    except Exception as e:
        print(f"Error conectando a Binance: {e}")
        return

    # 2. Obtener balance local de bots activos (RUNNING)
    active_bots = LiveBot.objects.all()
    sum_local_balances = Decimal("0")
    print("\nDetalle de Bots:")
    for bot in active_bots:
        sum_local_balances += bot.current_balance
        open_trades = LiveTrade.objects.filter(bot=bot, status='OPEN')
        trading_val = sum(t.amount * t.entry_price for t in open_trades)
        print(f"- {bot.name} ({bot.status}):")
        print(f"  Local Balance: {bot.current_balance}")
        print(f"  Capital en Trades Abiertos: {trading_val}")

    print(f"\nSuma Total Balances Locales: {sum_local_balances}")
    
    # 3. Comparación
    discrepancy = real_total - sum_local_balances
    print(f"\nDiscrepancia (Real - Local): {discrepancy}")
    
    if discrepancy < 0:
        print("¡ALERTA!: Tus bots creen tener más dinero del que hay en Binance.")
        print("Probablemente por compartir fondos entre bots o trades que no se cerraron correctamente en el exchange.")
    else:
        print("Tienes fondos suficientes no asignados a bots.")

if __name__ == "__main__":
    audit_balances()
