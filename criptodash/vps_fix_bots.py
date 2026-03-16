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
from dashboard.bot_manager import BotManager

def liquidate_stuck_trades():
    print("\n--- 🧹 Iniciando Liquidación de Trades Estancados ---")
    bots = LiveBot.objects.filter(status__in=['RUNNING', 'CLOSE_ONLY'])
    
    for bot in bots:
        print(f"\n  Bot: {bot.name} (ID: {bot.id}) | {bot.pair.symbol}")
        
        # Obtener precio actual
        df = BotManager._get_live_df(bot.pair.symbol, timeframe=bot.parameters.get('timeframe', '1h'))
        if df is None or df.empty:
            print(f"    ⚠️ No se pudo obtener precio para {bot.pair.symbol}. Saltando.")
            continue
            
        current_price = float(df['close'].iloc[-1])
        print(f"    Precio Actual: {current_price}")
        
        # Calcular grid_step
        grid_step = 0
        if bot.strategy_type == 'GRID':
            try:
                upper = float(bot.parameters.get('upper_price'))
                lower = float(bot.parameters.get('lower_price'))
                levels = int(bot.parameters.get('grid_levels'))
                grid_step = (upper - lower) / (levels - 1)
            except: pass

        # 1. Cerrar trades OPEN (Wait Sell) que ya pasaron su TP
        stuck_open = LiveTrade.objects.filter(bot=bot, status='OPEN')
        for t in stuck_open:
            target_tp = float(t.entry_price) + grid_step
            if current_price >= target_tp:
                print(f"    ✅ CERRANDO TRADE {t.id}: Precio {current_price} >= TP {target_tp:.4f}")
                BotManager._close_trade(t, current_price, "AUDIT_FIX_LIQUIDATION")
        
        # 2. Abrir trades WAITING (Wait Buy) que ya deberían haber entrado
        stuck_waiting = LiveTrade.objects.filter(bot=bot, status='WAITING')
        for t in stuck_waiting:
            if current_price <= float(t.entry_price):
                print(f"    ✅ ABRIENDO TRADE {t.id}: Precio {current_price} <= Entrada {t.entry_price}")
                t.status = 'OPEN'
                t.save()
            
            # 3. Cancelar trades WAITING que están fuera del rango actual (obsoletos)
            elif bot.strategy_type == 'GRID':
                lower_limit = float(bot.parameters.get('lower_price'))
                if float(t.entry_price) < (lower_limit - (grid_step * 1.5)):
                    print(f"    🗑️ CANCELANDO TRADE OBSOLETO {t.id}: Entrada {t.entry_price} fuera de rango ({lower_limit})")
                    t.status = 'CANCELED'
                    t.save()

def fix_vps_bots():
    print("🚀 Iniciando saneamiento de bots en VPS...")
    print("========================================")
    
    # 0. Liquidar trades estancados (Cierra simulaciones que ya ganaron/perdieron)
    liquidate_stuck_trades()

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
