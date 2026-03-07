import os
import django
import sys
from datetime import timedelta
from django.utils import timezone
from decimal import Decimal

# Setup Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "criptodash.settings")
django.setup()

from dashboard.models import LiveBot, LiveTrade

active_bots = LiveBot.objects.all()

print("--- ANALISIS DE BOTS ---")
for bot in active_bots:
    trades = LiveTrade.objects.filter(bot=bot)
    closed_trades = trades.filter(status='CLOSED')
    open_trades = trades.filter(status='OPEN')
    
    total_pnl = sum(t.pnl for t in trades)
    realized_pnl = sum(t.pnl for t in closed_trades)
    
    winning_trades = closed_trades.filter(pnl__gt=0).count()
    losing_trades = closed_trades.filter(pnl__lt=0).count()
    total_closed = closed_trades.count()
    
    win_rate = (winning_trades / total_closed * 100) if total_closed > 0 else 0
    
    print(f"\nBot: {bot.name} (ID: {bot.id}) - Pareja: {bot.pair.symbol if bot.pair else 'N/A'}")
    print(f"Estrategia: {bot.strategy_type}")
    print(f"Estado: {bot.status} | Is_Live: {bot.is_live}")
    print(f"Balance Inicial: {bot.initial_balance} | Balance Actual: {bot.current_balance}")
    print(f"Retorno Balance (calculado): {bot.current_balance - bot.initial_balance}")
    print(f"PNL Total (Trades): {total_pnl}")
    print(f"PNL Realizado (Cerrados): {realized_pnl}")
    print(f"Operaciones Cerradas: {total_closed} (Ganadoras: {winning_trades}, Perdedoras: {losing_trades})")
    print(f"Win Rate: {win_rate:.2f}%")
    print(f"Operaciones Abiertas: {open_trades.count()}")
    print(f"Parámetros: {bot.parameters}")
    
    if bot.last_error:
        print(f"Último Error: {bot.last_error}")

print("\n--- ULTIMOS 20 TRADES ---")
recent_trades = LiveTrade.objects.all().order_by('-updated_at')[:20]
for t in recent_trades:
    print(f"{t.updated_at.strftime('%Y-%m-%d %H:%M:%S')} | Bot: {t.bot.name} | {t.side} {t.amount} {t.bot.pair.symbol if t.bot.pair else 'N/A'} @ {t.entry_price} | Status: {t.status} | PNL: {t.pnl}")
