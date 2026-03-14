import os
import django

# Load .env manually if needed
def load_env():
    if os.path.exists('.env'):
        with open('.env') as f:
            for line in f:
                if '=' in line and not line.startswith('#'):
                    k, v = line.strip().split('=', 1)
                    os.environ[k] = v.strip('"').strip("'")
load_env()

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')
django.setup()

from dashboard.models import LiveBot

print("--- Applying Optimizations ---")

# 1. XRP Bot (Fixing Capital Mismatch)
try:
    xrp = LiveBot.objects.get(id=32)
    xrp.parameters['amount_per_level'] = '15'
    xrp.save()
    print(f"[OK] Bot {xrp.name} (ID 32): amount_per_level adjusted to 15.")
except Exception as e: print(f"[!] Error in xrpbot: {e}")

# 2. solbot2 (Extending Range)
try:
    sol = LiveBot.objects.get(id=3)
    sol.parameters['upper_price'] = '105'
    sol.parameters['trailing_enabled'] = True
    sol.save()
    print(f"[OK] Bot {sol.name} (ID 3): upper_price extended to 105 and Trailing Up enabled.")
except Exception as e: print(f"[!] Error in solbot2: {e}")

# 3. etcgrid (Improving Density)
try:
    etc = LiveBot.objects.get(id=27)
    etc.parameters['grid_levels'] = '5'
    etc.save()
    print(f"[OK] Bot {etc.name} (ID 27): grid_levels set to 5.")
except Exception as e: print(f"[!] Error in etcgrid: {e}")

# 4. DOTbot (Improving Density)
try:
    dot = LiveBot.objects.get(id=29)
    dot.parameters['grid_levels'] = '5'
    dot.save()
    print(f"[OK] Bot {dot.name} (ID 29): grid_levels set to 5.")
except Exception as e: print(f"[!] Error in DOTbot: {e}")

# 5. UNI (Improving Density)
try:
    uni = LiveBot.objects.get(id=30)
    uni.parameters['grid_levels'] = '5'
    uni.save()
    print(f"[OK] Bot {uni.name} (ID 30): grid_levels set to 5.")
except Exception as e: print(f"[!] Error in UNI: {e}")

print("\n[FINISH] Optimizations applied. Remember to RESTART your VPS services/server.")
