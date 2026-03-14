import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')
django.setup()

from dashboard.models import LiveBot

print("--- Analysis of GRID bots ---")
grid_bots = LiveBot.objects.filter(strategy_type='GRID')
required = ['upper_price', 'lower_price', 'grid_levels', 'amount_per_level']

for bot in grid_bots:
    print(f"\nBot: {bot.name} (ID: {bot.id}) | Status: {bot.status}")
    params = bot.parameters or {}
    missing = []
    for p in required:
        val = params.get(p)
        if val is None or val == '':
            missing.append(p)
    
    if missing:
        print(f"  [!] MISSING PARAMS: {missing}")
    else:
        print(f"  [OK] All required params present.")
    
    print(f"  Params: {params}")
