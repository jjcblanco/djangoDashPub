#!/usr/bin/env python3
"""
Test whale signal service integration.
"""
import os
import sys
import django

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')
django.setup()

from dashboard.whale_signal_service import WhaleSignalService
from dashboard.models import LiveBot

def main():
    print("=== Whale Signal Service Test ===\n")
    
    # Get all day trading bots
    day_bots = LiveBot.objects.filter(strategy_type='DAYTRADING', status='RUNNING')
    print(f"Found {day_bots.count()} day trading bots")
    
    for bot in day_bots:
        print(f"\n--- Bot {bot.id}: {bot.name} ({bot.pair.symbol}) ---")
        
        # Get whale signal for this pair
        signal = WhaleSignalService.get_signal(bot.pair.symbol)
        print(f"  Signal: {signal['signal']}")
        print(f"  Confidence: {signal['confidence']:.2f}")
        print(f"  Sources: {signal['sources']}")
        
        # Show details
        if signal['details']:
            print(f"  Details:")
            for key, val in signal['details'].items():
                if isinstance(val, dict):
                    print(f"    {key}:")
                    for k2, v2 in val.items():
                        print(f"      {k2}: {v2}")
                else:
                    print(f"    {key}: {val}")
        
        # Determine if signal should influence bot
        if signal['signal'] != 'HOLD' and signal['confidence'] > 0.7:
            print(f"  \u2192 Strong whale signal detected! Could override bot strategy.")
            # Here we would integrate with bot decision logic
            # For example, adjust parameters or trigger immediate action
    
    # Test specific pairs
    print("\n=== Testing specific pairs ===")
    test_pairs = ['SOL/USDT', 'ETH/USDT', 'BNB/USDT', 'XRP/USDT']
    for pair in test_pairs:
        signal = WhaleSignalService.get_signal(pair)
        print(f"{pair}: {signal['signal']} (confidence: {signal['confidence']:.2f})")

if __name__ == '__main__':
    main()