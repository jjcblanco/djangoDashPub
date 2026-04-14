import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + '/../criptodash')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')
import django
django.setup()
from dashboard.whale_pattern_learner import WhalePatternLearner
from dashboard.models import WhalePattern
print("Testing Whale Pattern Learning...")
patterns = WhalePatternLearner.analyze_trades(min_trades=1, min_win_rate=0.6)
print(f'Found {len(patterns)} patterns')
active = WhalePattern.objects.filter(is_active=True).count()
print(f'Active patterns in DB: {active}')
for p in patterns[:5]:
    print(f"  - {p.pattern_name}: win_rate={p.win_rate:.2f} avg_pnl={p.avg_pnl:.2f}")