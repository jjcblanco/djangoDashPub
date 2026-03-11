import os
import sys
import django
from decimal import Decimal

# Añadir el directorio del proyecto al path
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')

try:
    django.setup()
    from dashboard.models import LiveBot, LiveTrade, TradingPair, CapitalFunding, GlobalSettings
    from dashboard.views.bot_views import bot_dashboard
    
    print("SUCCESS: Modelos y vistas cargados correctamente.")
    
    # Intentar obtener o crear GlobalSettings para verificar la BD
    gs, created = GlobalSettings.objects.get_or_create(id=1)
    print(f"SUCCESS: GlobalSettings (ID=1) accesible. Creado: {created}")
    print(f"Campos: DD={gs.max_drawdown_pct}, Telegram={gs.notifications_enabled}")
    
except Exception as e:
    print(f"ERROR CRÍTICO: {e}")
    import traceback
    traceback.print_exc()
