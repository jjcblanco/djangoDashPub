import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'criptodash'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')
import django
django.setup()
from dashboard.models import LiveBot
bots = LiveBot.objects.filter(is_live=True)
for b in bots:
    print(f'Bot {b.id}: {float(b.current_balance)}')
print(f'Total: {sum(float(b.current_balance) for b in bots)}')