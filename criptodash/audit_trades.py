import os
import django
from django.utils import timezone

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')
django.setup()

from dashboard.models import LiveTrade

def check_trades():
    trades = LiveTrade.objects.all().order_by('-id')[:5]
    print(f"{'ID':<5} | {'Status':<10} | {'Entry Time':<20} | {'Updated At':<20}")
    print("-" * 65)
    for t in trades:
        print(f"{t.id:<5} | {t.status:<10} | {str(t.entry_time):<20} | {str(t.updated_at):<20}")

if __name__ == "__main__":
    check_trades()
