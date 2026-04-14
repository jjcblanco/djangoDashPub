#!/usr/bin/env python3
"""
Run whale pattern learning and extract patterns from successful whale trades.
"""
import os
import sys
import django

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')
django.setup()

from dashboard.whale_pattern_learner import WhalePatternLearner
from dashboard.models import WhalePattern

def main():
    print("=== Whale Pattern Learning ===")
    
    # Analyze trades
    print("Analyzing whale trades...")
    patterns = WhalePatternLearner.analyze_trades(min_trades=1, min_win_rate=0.6)
    
    print(f"Found {len(patterns)} patterns")
    for i, pattern in enumerate(patterns):
        print(f"\nPattern {i+1}: {pattern.pattern_name}")
        print(f"  Conditions: {pattern.conditions}")
        print(f"  Avg PnL: {pattern.avg_pnl:.2f}%")
        print(f"  Win rate: {pattern.win_rate:.2f}%")
        print(f"  Sample size: {pattern.sample_size}")
    
    # Display top patterns in database
    top_patterns = WhalePattern.objects.filter(sample_size__gte=1).order_by('-avg_pnl')
    print(f"\nTop patterns in database: {top_patterns.count()}")
    for p in top_patterns[:10]:
        print(f"  {p.pattern_name}: {p.avg_pnl:.2f}% PnL, {p.win_rate:.2f}% win rate, n={p.sample_size}")
    
    # Test signal generation with sample context
    print("\n=== Testing Signal Generation ===")
    # Get a sample context from a recent trade
    from dashboard.models import ShadowTrade
    trade = ShadowTrade.objects.filter(market_context__isnull=False).first()
    if trade:
        print(f"Testing with symbol: {trade.token_symbol}")
        signal = WhalePatternLearner.generate_signal(trade.token_symbol, trade.market_context)
        print(f"Signal: {signal['signal']} (confidence: {signal['confidence']:.2f})")
        print(f"Matched patterns: {len(signal['matched_patterns'])}")
        for mp in signal['matched_patterns']:
            print(f"  - {mp['pattern']}: win_rate={mp['win_rate']:.2f}, confidence={mp['confidence']:.2f}")
    else:
        print("No shadow trades with market context available.")

if __name__ == '__main__':
    main()