import os
import django
import traceback

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')
django.setup()

from dashboard.models import ScalpingBot
from dashboard.tasks import run_scalping_bot_task

print("TESTING TODOS LOS BOTS...")
bots = ScalpingBot.objects.all()

for bot in bots:
    print(f"\n--- Probando Bot {bot.id} {bot.name} ---")
    try:
        # Simulamos forzar la evaluacion de cada bot para descubrir el error JSON
        res = run_scalping_bot_task(bot.id, force_eval=True)
        print("Resultado:", res)
        # Tambien probamos si al sacar serialize del trade falla
    except Exception as e:
        print("EXCEPCION ATRAPADA POR EL TESTER:")
        traceback.print_exc()
