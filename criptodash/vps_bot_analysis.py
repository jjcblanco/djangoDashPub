import os
import django
from django.db.models import Count, Sum

# --- CONFIGURACIÓN PARA EVITAR ERRORES DE DECOUPLE (.env) ---
# Inyectamos una clave falsa para que Django no se queje de SECRET_KEY
os.environ['SECRET_KEY'] = 'fake-key-para-scripts-123'
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')
django.setup()

from dashboard.models import LiveBot, LiveTrade

bots = LiveBot.objects.all()
print(f"Total Bots en VPS: {bots.count()}\n" + "="*40 + "\n")

for bot in bots:
    print(f"--- BOT: {bot.name} (ID: {bot.id}) ---")
    print(f"  Estado: {bot.status} | Estrategia: {bot.strategy_type} | Par: {bot.pair.symbol}")
    print(f"  Balance Inicial: {bot.initial_balance} | Actual: {bot.current_balance}")
    
    pnl_total = bot.current_balance - bot.initial_balance
    color = "\033[92m" if pnl_total > 0 else ("\033[91m" if pnl_total < 0 else "\033[0m")
    print(f"  Retorno Neto: {color}{pnl_total:.8f}\033[0m")
    
    trades = LiveTrade.objects.filter(bot=bot)
    closed = trades.filter(status='CLOSED')
    
    winners = closed.filter(pnl__gt=0).count()
    losers = closed.filter(pnl__lt=0).count()
    total_closed = closed.count()
    
    winrate = (winners / total_closed * 100) if total_closed > 0 else 0
    
    print(f"  Trades Cerrados: {total_closed} | Abiertos (En curso): {trades.filter(status='OPEN').count()}")
    print(f"  WinRate: {winrate:.2f}% ({winners} G / {losers} P)")
    print(f"  Parámetros: {bot.parameters}")
    print("-" * 40 + "\n")

