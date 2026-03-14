import os
import sys

# 1. Intentar cargar .env manualmente si falla decouple
def load_env_manually():
    try:
        with open('.env') as f:
            for line in f:
                if line.strip() and not line.startswith('#'):
                    key, value = line.strip().split('=', 1)
                    os.environ[key] = value.strip('"').strip("'")
        print("[OK] .env cargado manualmente.")
    except Exception as e:
        print(f"[!] Error cargando .env: {e}")

load_env_manually()

# 2. Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')
try:
    import django
    django.setup()
except Exception as e:
    print(f"[ERROR CRÍTICO] No se pudo iniciar Django: {e}")
    sys.exit(1)

from dashboard.models import LiveBot

print("\n--- Diagnóstico de Bots GRID ---")
bots = LiveBot.objects.filter(strategy_type='GRID')
for b in bots:
    p = b.parameters or {}
    amount = p.get('amount_per_level')
    print(f"ID: {b.id} | Nombre: {b.name} | Status: {b.status}")
    print(f"  > amount_per_level: {amount} (Tipo: {type(amount)})")
    if amount is None:
        print("  [!!!] ERROR: Este parámetro falta. Reparando...")
        b.parameters['amount_per_level'] = '10'  # Valor por defecto seguro
        b.save()
        print("  [FIX] Parámetro restaurado a '10'.")

print("\n--- Verificación de Versión de Código ---")
import inspect
from dashboard.bot_manager import BotManager
source = inspect.getsource(BotManager._manage_grid_bot)
if 'safe_float' in source:
    print("[OK] El código del VPS tiene la versión corregida (con safe_float).")
else:
    print("[!] AVISO: El código del VPS sigue siendo la VERSIÓN ANTIGUA.")
    print("    DEBES ejecutar 'git reset --hard origin/main' y REINICIAR el servidor.")
