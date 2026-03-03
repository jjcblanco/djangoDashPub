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
    from ..ccxttest1 import binance as exchange
    
    bots = LiveBot.objects.all().order_by('-created_at')
    available_pairs = TradingPair.objects.filter(is_active=True)
    
    # Calcular stats rápidas para cada bot
    bots_data = []
    for bot in bots:
        trades = LiveTrade.objects.filter(bot=bot)
        total_pnl = sum(t.pnl for t in trades)
        active_trades_query = trades.filter(status='OPEN')
        active_trades_count = active_trades_query.count()
        
        # Calcular Break-even (Precio promedio de entrada de lo que está abierto)
        total_qty = sum(t.amount for t in active_trades_query)
        total_cost = sum(t.amount * t.entry_price for t in active_trades_query)
        break_even = float(total_cost / total_qty) if total_qty > 0 else None
        
        bots_data.append({
            'bot': bot,
            'total_pnl': total_pnl,
            'active_trades': active_trades_count,
            'break_even': break_even,
            'profit_pct': (total_pnl / bot.initial_balance * 100) if bot.initial_balance > 0 else 0
        })

    # Calcular métricas globales
    global_invested = sum(b.initial_balance for b in bots)
    global_pnl = sum(d['total_pnl'] for d in bots_data)
    global_roi = (global_pnl / global_invested * 100) if global_invested > 0 else 0

    # Obtener las últimas 50 operaciones globales para el historial
    recent_trades = list(LiveTrade.objects.all().order_by('-entry_time')[:50])
    
    # Obtener precios actuales para los símbolos involucrados
    symbols = list(set([t.bot.pair.symbol for t in recent_trades if t.status == 'OPEN']))
    current_prices = {}
    if symbols:
        try:
            # Añadir un timeout corto para no colgar la vista principal
            exchange.timeout = 5000  # 5 segundos
            tickers = exchange.fetch_tickers(symbols)
            current_prices = {s: tickers[s]['last'] for s in symbols if s in tickers}
        except Exception as e:
            print(f"Error fetching tickers in dashboard: {e}")

    # Enriquecer trades para la vista
    for trade in recent_trades:
        if trade.status == 'OPEN':
            symbol = trade.bot.pair.symbol
            trade.current_price = current_prices.get(symbol)
            
            # Calcular precio objetivo para Grid
            if trade.bot.strategy_type == 'GRID':
                params = trade.bot.parameters
                try:
                    upper = float(params.get('upper_price', 0))
                    lower = float(params.get('lower_price', 0))
                    levels = int(params.get('grid_levels', 2))
                    if levels > 1:
                        grid_step = (upper - lower) / (levels - 1)
                        trade.target_price = float(trade.entry_price) + grid_step
                except (ValueError, TypeError):
                    trade.target_price = None

    # Obtener balance real de Binance
    exchange_balance = None
    try:
        bal = exchange.fetch_balance()
        exchange_balance = {
            'free': bal['free'].get('USDT', 0),
            'total': bal['total'].get('USDT', 0),
            'used': bal['used'].get('USDT', 0)
        }
    except Exception as e:
        print(f"Error fetching balance: {e}")

    context = {
        'bots_data': bots_data,
        'recent_trades': recent_trades,
        'available_pairs': available_pairs,
        'strategy_types': LiveBot.STRATEGY_CHOICES,
        'exchange_balance': exchange_balance,
        'global_metrics': {
            'invested': global_invested,
            'pnl': global_pnl,
            'roi': global_roi
        }
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
        timeframe = request.POST.get('timeframe', '1h')
        
        # Extraer parámetros dinámicos según estrategia
        params = {'timeframe': timeframe}
        if strategy_type == 'GRID':
            params = {
                'upper_price': request.POST.get('upper_price'),
                'lower_price': request.POST.get('lower_price'),
                'grid_levels': request.POST.get('grid_levels'),
                'amount_per_level': request.POST.get('amount_per_level'),
                'global_stop_loss': request.POST.get('global_stop_loss'),
                'trailing_enabled': request.POST.get('trailing_enabled') == 'on',
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
        elif action == 'close_only':
            bot.status = 'CLOSE_ONLY'
            bot.save()
            messages.info(request, f"Bot '{bot.name}' en modo SOLO CIERRE (Se venderá lo abierto, no se comprará más).")
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
    try:
        print(f"DEBUG: Iniciando actualización manual de bots para usuario {request.user}")
        results = BotManager.update_all_active_bots()
        print(f"DEBUG: Actualización completada. Bots procesados: {len(results)}")
        return JsonResponse({
            'status': 'ok', 
            'updated_count': len(results), 
            'results': results
        })
    except Exception as e:
        print(f"ERROR en trigger_bot_update: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
