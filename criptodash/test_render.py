import os
import sys
import django
from django.template import Template, Context
from decimal import Decimal

# Añadir el directorio del proyecto al path
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')

try:
    django.setup()
    from dashboard.models import GlobalSettings
    
    path = 'dashboard/templates/dashboard/bot_dashboard.html'
    if not os.path.exists(path):
        path = 'criptodash/dashboard/templates/dashboard/bot_dashboard.html'
        
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    t = Template(content)
    gs, _ = GlobalSettings.objects.get_or_create(id=1)
    
    # Mock context
    context = Context({
        'bots_data': [],
        'recent_trades': [],
        'available_pairs': [],
        'global_settings': gs,
        'global_metrics': {'invested': 0, 'pnl': 0, 'roi': 0, 'commission': 0},
        'exchange_balance': {'free': 0, 'total': 0, 'used': 0},
        'over_allocated': False,
        'real_total': Decimal("0"),
        'total_injected_capital': Decimal("0"),
        'real_net_profit': Decimal("0"),
        'funding_history': [],
        'global_assigned': Decimal("0")
    })
    
    print("Iniciando renderizado...")
    t.render(context)
    print("SUCCESS: Renderizado completo sin errores.")
    
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
