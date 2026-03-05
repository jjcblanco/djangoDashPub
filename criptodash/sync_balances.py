import os
import django
import sys
from decimal import Decimal

# Setup Django
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')
django.setup()

from dashboard.models import LiveBot, LiveTrade
from dashboard.ccxttest1 import binance as exchange

def sync_balances():
    print("--- Iniciando Sincronización Proporcional de Balances ---")
    
    # 1. Obtener balance real de Binance
    try:
        bal = exchange.fetch_balance()
        real_total = Decimal(str(bal['total'].get('USDT', 0)))
        print(f"Saldo Real en Binance: ${real_total} USDT")
    except Exception as e:
        print(f"Error conectando a Binance: {e}")
        return

    if real_total <= 0:
        print("Error: No hay fondos reales en Binance para sincronizar.")
        return

    # 2. Obtener todos los bots que no están detenidos o tienen balance positivo
    bots = LiveBot.objects.all()
    total_local_assigned = sum(b.current_balance for b in bots)
    
    if total_local_assigned <= 0:
        print("No hay balance local asignado a bots para redistribuir.")
        # Podríamos asignar el saldo real equitativamente, pero mejor esperar a órdenes del usuario
        return

    print(f"Total Local Actual: ${total_local_assigned}")
    
    # 3. Calcular factor de ajuste
    # Si tenemos $10 real y $100 local, el factor es 0.1
    ratio = real_total / total_local_assigned
    print(f"Factor de ajuste: {ratio:.4f}")

    # 4. Aplicar ajuste
    for bot in bots:
        old_balance = bot.current_balance
        new_balance = old_balance * ratio
        
        # Redondear a 8 decimales para evitar problemas con DecimalField
        bot.current_balance = new_balance.quantize(Decimal("1.00000000"))
        # También ajustamos el initial_balance para que el ROI tenga sentido histórico relativo
        bot.initial_balance = (bot.initial_balance * ratio).quantize(Decimal("1.00000000"))
        bot.save()
        
        print(f"Bot '{bot.name}': ${old_balance:.2f} -> ${bot.current_balance:.2f} USDT")

    print("\nSincronización completada con éxito.")

if __name__ == "__main__":
    sync_balances()
