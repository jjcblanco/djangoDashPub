import os
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')
django.setup()

from dashboard.models import ScalpingBot
from dashboard.tasks import run_scalping_bot_task

print("====================================")
print("🔍 DEBUGGER DE BOTS EN PRODUCCION")
print("====================================\n")

bots_en_error = ScalpingBot.objects.filter(last_error__icontains="JSON")

print(f"Hay {bots_en_error.count()} bots marcados con error JSON en la DB.")

# Forzamos evaluación para atrapar exactamente DÓNDE falla
for bot in bots_en_error:
    print(f"\n[{bot.pair.symbol}] Probando {bot.strategy_type}...")
    try:
        # Borramos el error para hacer una prueba limpia
        bot.last_error = None
        bot.save()
        
        # Evaluamos
        res = run_scalping_bot_task(bot.id, force_eval=True)
        bot.refresh_from_db()
        
        if bot.last_error and "JSON" in bot.last_error:
            print(f"❌ ¡FALLÓ DE NUEVO! El error sigue pasando para {bot.strategy_type}.")
        else:
            print(f"✅ ÉXITO. El bot se ejecutó sin errores JSON.")
    except Exception as e:
        print(f"💥 EXC {e}")

print("\nSi dice ÉXITO pero el error en la web volvía a salir es porque CELERY TIENE EL CÓDIGO VIEJO.")
