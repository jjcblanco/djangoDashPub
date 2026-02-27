from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from ..models import LiveBot, LiveTrade, TradingPair
from ..bot_manager import BotManager
import json
from decimal import Decimal

@login_required
def bot_dashboard(request):
    """Vista principal para gestionar bots."""
    bots = LiveBot.objects.all().order_by('-created_at')
    available_pairs = TradingPair.objects.filter(is_active=True)
    
    # Calcular stats rápidas para cada bot
    bots_data = []
    for bot in bots:
        trades = LiveTrade.objects.filter(bot=bot)
        total_pnl = sum(t.pnl for t in trades)
        active_trades = trades.filter(status='OPEN').count()
        
        bots_data.append({
            'bot': bot,
            'total_pnl': total_pnl,
            'active_trades': active_trades,
            'profit_pct': (total_pnl / bot.initial_balance * 100) if bot.initial_balance > 0 else 0
        })

    # Obtener las últimas 50 operaciones globales para el historial
    recent_trades = LiveTrade.objects.all().order_by('-entry_time')[:50]

    context = {
        'bots_data': bots_data,
        'recent_trades': recent_trades,
        'available_pairs': available_pairs,
        'strategy_types': LiveBot.STRATEGY_CHOICES
    }
    return render(request, 'dashboard/bot_dashboard.html', context)

@login_required
@require_POST
def create_bot(request):
    """Crea una nueva instancia de bot."""
    try:
        name = request.POST.get('name')
        pair_id = request.POST.get('pair')
        strategy_type = request.POST.get('strategy_type')
        balance = request.POST.get('balance')
        
        # Extraer parámetros dinámicos según estrategia
        params = {}
        if strategy_type == 'GRID':
            params = {
                'upper_price': request.POST.get('upper_price'),
                'lower_price': request.POST.get('lower_price'),
                'grid_levels': request.POST.get('grid_levels'),
                'amount_per_level': request.POST.get('amount_per_level'),
                'global_stop_loss': request.POST.get('global_stop_loss'),
            }
        elif strategy_type == 'DAYTRADING':
            params = {
                'min_strength': request.POST.get('min_strength', 3),
                'min_adx': request.POST.get('min_adx', 20),
            }

        pair = TradingPair.objects.get(id=pair_id)
        is_live = request.POST.get('is_live') == 'on'
        
        bot = LiveBot.objects.create(
            name=name,
            pair=pair,
            strategy_type=strategy_type,
            parameters=params,
            initial_balance=Decimal(balance),
            current_balance=Decimal(balance),
            status='STOPPED',
            is_live=is_live
        )
        
        messages.success(request, f"Bot '{name}' creado exitosamente.")
    except Exception as e:
        messages.error(request, f"Error al crear bot: {e}")
    
    return redirect('bot_dashboard')

@login_required
@require_POST
def bot_action(request, bot_id):
    """Controla el estado del bot (start/stop/delete)."""
    action = request.POST.get('action')
    try:
        bot = LiveBot.objects.get(id=bot_id)
        
        if action == 'start':
            bot.status = 'RUNNING'
            bot.save()
            messages.success(request, f"Bot '{bot.name}' iniciado.")
        elif action == 'stop':
            bot.status = 'STOPPED'
            bot.save()
            messages.success(request, f"Bot '{bot.name}' detenido.")
        elif action == 'clear_error':
            bot.last_error = None
            bot.status = 'STOPPED'
            bot.save()
            messages.success(request, f"Error de '{bot.name}' limpiado. Estado reseteado a STOPPED.")
        elif action == 'delete':
            bot.delete()
            messages.success(request, "Bot eliminado.")
            
    except Exception as e:
        messages.error(request, f"Error: {e}")
        
    return redirect('bot_dashboard')

@login_required
def trigger_bot_update(request):
    """Fuerza una actualización de todos los bots activos."""
    results = BotManager.update_all_active_bots()
    return JsonResponse({'status': 'ok', 'updated_count': len(results), 'results': results})
