import os
import django
import sys
from decimal import Decimal

# Configurar entorno Django (Asegúrate de estar en el CWD correcto)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')
django.setup()

from dashboard.models import LiveBot, LiveTrade
from django.db.models import Sum

def recalibrate_all_bots():
    print("--- 🚀 Iniciando Recalibración de Bots ---")
    bots = LiveBot.objects.all()
    
    for bot in bots:
        print(f"\nProcessing Bot: {bot.name} (ID: {bot.id})")
        
        # 1. Calcular capital necesario según mallas (Si es GRID)
        if bot.strategy_type == 'GRID':
            try:
                levels = int(bot.parameters.get('grid_levels', 0))
                amount = float(bot.parameters.get('amount_per_level', 0))
                ideal_capital = Decimal(str(levels * amount))
                
                # Si el capital inicial era una cifra simbólica (dust), lo subimos a lo real
                if bot.initial_balance < ideal_capital:
                    print(f"  - Actualizando Initial Balance: {bot.initial_balance} -> {ideal_capital}")
                    bot.initial_balance = ideal_capital
            except Exception as e:
                print(f"  - Error calculando capital ideal: {e}")

        # 2. Calcular PnL Realizado (Cerrados)
        realized_pnl = LiveTrade.objects.filter(bot=bot).exclude(status__in=['OPEN', 'WAITING']).aggregate(total=Sum('pnl'))['total'] or Decimal("0")
        
        # 3. Calcular Capital actualmente "En Juego" (Órdenes Abiertas o en Espera)
        # En nuestro sistema, el costo se deduce al poner la orden.
        # Capital_En_Juego = Sum(Trade_Abierto.entry_price * Trade_Abierto.amount)
        open_trades = LiveTrade.objects.filter(bot=bot, status__in=['OPEN', 'WAITING'])
        
        capital_in_orders = Decimal("0")
        for t in open_trades:
            # Aproximamos el costo por el entry_price
            capital_in_orders += t.entry_price * t.amount
            
        # 4. RECALIBRAR current_balance
        # El balance actual DEBERÍA SER: Initial + Realized - Invested
        new_current = bot.initial_balance + realized_pnl - capital_in_orders
        
        if new_current < 0:
            print(f"  - ⚠️ Advertencia: Balance calculado sigue siendo Negativo ({new_current}). Ajustando a 1.0 (reserva técnica).")
            # Esto sucede si el bot tuvo más pérdidas de las que el initial_balance soporta
            # o si las comisiones se comieron el capital.
            # No lo dejamos negativo para que el manager no muera.
            bot.current_balance = Decimal("1.0") 
        else:
            print(f"  - Sincronizando Current Balance: {bot.current_balance} -> {new_current}")
            bot.current_balance = new_current
            
        bot.save()
        print(f"  - ✅ Bot {bot.id} recalibrado.")

if __name__ == "__main__":
    recalibrate_all_bots()
