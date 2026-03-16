import os
import django
import sys
from decimal import Decimal

# Configuración de Django
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)

# Carga manual de .env para evitar problemas con decouple en scripts standalone
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

def fix_vps_bots():
    print("🚀 Iniciando saneamiento de bots en VPS...")
    print("========================================")

    # 1. Corregir etcgrid (ID: 27)
    try:
        etcgrid = LiveBot.objects.get(id=27)
        print(f"\n--- Corrigiendo etcgrid (ID: 27) ---")
        print(f"  Balance anterior: {etcgrid.current_balance}")
        
        # Reset balance a 10.0 si es negativo o muy bajo
        if etcgrid.current_balance < 1:
            etcgrid.current_balance = Decimal('10.0')
            print(f"  ✅ Balance reseteado a 10.0 USDT.")

        # Corregir Stop Loss absurdo
        params = etcgrid.parameters or {}
        old_sl = params.get('global_stop_loss')
        try:
            val_sl = float(old_sl) if old_sl else 0
            if val_sl < 100: # Claramente erróneo para ETH
                params['global_stop_loss'] = '2200.0'
                etcgrid.parameters = params
                print(f"  ✅ Stop Loss corregido de {old_sl} a 2200.0")
        except:
            pass
        
        etcgrid.save()
    except LiveBot.DoesNotExist:
        print("⚠️ etcgrid (ID: 27) no encontrado.")

    # 2. Recalcular P&L para solbot2 (ID: 3)
    try:
        solbot = LiveBot.objects.get(id=3)
        print(f"\n--- Auditando solbot2 (ID: 3) ---")
        closed_trades = LiveTrade.objects.filter(bot=solbot, status__in=['CLOSED', 'CLOSED_EMERGENCY'])
        total_pnl = sum(t.pnl for t in closed_trades if t.pnl)
        
        print(f"  Trades cerrados encontrados: {closed_trades.count()}")
        print(f"  PnL Acumulado calculado: {total_pnl}")
        
        if total_pnl > 0 and solbot.current_balance == solbot.initial_balance:
            solbot.current_balance = solbot.initial_balance + total_pnl
            print(f"  ✅ Balance actualizado con PnL: {solbot.current_balance}")
            solbot.save()
        else:
            print("  ℹ️ No se detectaron discrepancias o ya está balanceado.")
    except LiveBot.DoesNotExist:
        print("⚠️ solbot2 (ID: 3) no encontrado.")

    # 3. Limpiar estado de ERROR en etcbotprueba (ID: 26)
    try:
        etcerror = LiveBot.objects.get(id=26)
        if etcerror.status == 'ERROR':
            print(f"\n--- Limpiando ERROR en etcbotprueba (ID: 26) ---")
            etcerror.status = 'STOPPED'
            etcerror.last_error = f"Audit Fix: Reset desde ERROR. Mensaje previo: {etcerror.last_error}"
            etcerror.save()
            print("  ✅ Estado cambiado a STOPPED.")
    except LiveBot.DoesNotExist:
        print("⚠️ etcbotprueba (ID: 26) no encontrado.")

    # 4. Reporte de Liquidez Crítica
    print("\n--- Reporte de Liquidez Crítica (Balances < 1 USD) ---")
    low_liq = LiveBot.objects.filter(current_balance__lt=1)
    if low_liq.exists():
        for b in low_liq:
            print(f"  ❌ Bot: {b.name} (ID: {b.id}) | Balance: {b.current_balance} USDT")
        print("\n💡 Sugerencia: Elimina estos bots o inyéctales capital para que puedan operar.")
    else:
        print("  ✅ Todos los bots tienen balance positivo > 1 USDT.")

    print("\n========================================")
    print("✅ Saneamiento completado.")

if __name__ == "__main__":
    fix_vps_bots()
