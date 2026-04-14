#!/usr/bin/env python3
"""
Inspect shadow trades to understand data availability.
"""
import os
import sys
import django
import json

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')
django.setup()

from dashboard.models import ShadowTrade, WhaleWallet

closed_trades = ShadowTrade.objects.filter(status='CLOSED')
print(f'Closed shadow trades: {closed_trades.count()}')
open_trades = ShadowTrade.objects.filter(status='OPEN')
print(f'Open shadow trades: {open_trades.count()}')

if closed_trades.exists():
    trade = closed_trades.first()
    print(f'Sample trade: {trade.token_symbol}, PnL: {trade.pnl_percent}%')
    if trade.market_context:
        print('Market context keys:', list(trade.market_context.keys()))
        # Print some values
        for k, v in trade.market_context.items():
            if isinstance(v, (int, float, str)):
                print(f'  {k}: {v}')
    else:
        print('No market context')
    
    # Analyze PnL distribution
    pnls = [t.pnl_percent for t in closed_trades]
    print(f'PnL range: {min(pnls):.2f}% to {max(pnls):.2f}%')
    print(f'Average PnL: {sum(pnls)/len(pnls):.2f}%')
    positive = sum(1 for p in pnls if p > 0)
    print(f'Win rate: {positive/len(pnls)*100:.1f}%')
else:
    print('No closed trades yet. Need to wait for whales to sell.')

# Check whale wallets
wallets = WhaleWallet.objects.all()
print(f'\nTotal whale wallets: {wallets.count()}')
for w in wallets[:5]:
    print(f'  {w.id}: {w.name or w.address[:8]} - {w.blockchain}')