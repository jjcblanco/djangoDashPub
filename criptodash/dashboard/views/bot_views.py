from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.db import models
from django.db.models import Sum
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from ..models import LiveBot, LiveTrade, TradingPair, CapitalFunding, GlobalSettings
from ..bot_manager import BotManager
import json
from decimal import Decimal

@login_required
def bot_dashboard(request):
    """Vista principal para gestionar bots con diagnóstico de errores."""
    try:
        from ..ccxttest1 import binance as exchange
        
        bots = LiveBot.objects.all().order_by('-created_at')
        available_pairs = TradingPair.objects.filter(is_active=True)
        global_settings, _ = GlobalSettings.objects.get_or_create(id=1)
        
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
        global_assigned = sum(b.current_balance for b in bots)
        global_pnl = sum(d['total_pnl'] for d in bots_data)
        global_roi = (global_pnl / global_invested * 100) if global_invested > 0 else 0
        global_commission = LiveTrade.objects.aggregate(total=Sum('commission'))['total'] or Decimal("0")

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
        over_allocated = False
        real_total = Decimal("0")
        try:
            bal = exchange.fetch_balance()
            real_total = Decimal(str(bal['total'].get('USDT', 0)))
            exchange_balance = {
                'free': bal['free'].get('USDT', 0),
                'total': float(real_total),
                'used': bal['used'].get('USDT', 0)
            }
            # Si lo que los bots "creen" que tienen supera lo que hay en Binance por más de 1 USDT
            if global_assigned > real_total + Decimal("1.0"):
                over_allocated = True
        except Exception as e:
            print(f"Error fetching balance: {e}")

        # Calcular capital total inyectado (histórico)
        total_injected_capital = CapitalFunding.objects.aggregate(total=models.Sum('amount'))['total'] or Decimal("0")
        funding_history = CapitalFunding.objects.all().order_by('-funding_date')[:10]
        
        # Calcular Beneficio Real Absoluto (Saldo Actual - Capital Inyectado)
        real_net_profit = Decimal("0")
        if exchange_balance:
            real_net_profit = real_total - total_injected_capital

        context = {
            'bots_data': bots_data,
            'recent_trades': recent_trades,
            'available_pairs': available_pairs,
            'strategy_types': LiveBot.STRATEGY_CHOICES,
            'exchange_balance': exchange_balance,
            'over_allocated': over_allocated,
            'real_total': real_total,
            'global_assigned': global_assigned,
            'total_injected_capital': total_injected_capital,
            'real_net_profit': real_net_profit,
            'funding_history': funding_history,
            'global_metrics': {
                'invested': global_invested,
                'pnl': global_pnl,
                'roi': global_roi,
                'commission': float(global_commission)
            },
            'global_settings': global_settings
        }
        return render(request, 'dashboard/bot_dashboard.html', context)
    except Exception as e:
        import traceback
        error_msg = f"<h3>Error 500 en Dashboard</h3><p><b>{str(e)}</b></p><pre>{traceback.format_exc()}</pre>"
        return HttpResponse(error_msg, status=500)

@login_required
@require_POST
def add_funding(request):
    """Registra una nueva inyección de capital (transferencia, depósito, etc.)."""
    try:
        amount = request.POST.get('amount')
        description = request.POST.get('description')
        if amount:
            CapitalFunding.objects.create(
                amount=Decimal(amount),
                description=description
            )
            messages.success(request, f"Inyección de ${amount} USDT registrada con éxito.")
    except Exception as e:
        messages.error(request, f"Error al registrar inversión: {e}")
    
    return redirect('bot_dashboard')

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
                'trailing_down': request.POST.get('trailing_down') == 'on',
            }
        elif strategy_type == 'DAYTRADING':
            params = {
                'min_strength': request.POST.get('min_strength', 3),
                'min_adx': request.POST.get('min_adx', 20),
                'allow_late_entry': request.POST.get('allow_late_entry') == 'on',
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

@login_required
def trigger_balance_sync(request):
    """
    Sincroniza los balances de los bots con el saldo real de Binance
    proporcionalmente, para evitar sobre-asignación.
    """
    from ..ccxttest1 import binance as exchange
    
    try:
        # 1. Obtener balance real
        bal = exchange.fetch_balance()
        real_total = Decimal(str(bal['total'].get('USDT', 0)))
        
        if real_total <= 0:
            messages.error(request, "No se encontraron fondos reales en Binance para sincronizar.")
            return redirect('bot_dashboard')
            
        # 2. Calcular total local
        bots = LiveBot.objects.all()
        total_local_assigned = sum(b.current_balance for b in bots)
        
        if total_local_assigned <= 0:
            messages.warning(request, "No hay saldo local asignado a ningún bot para sincronizar.")
            return redirect('bot_dashboard')
            
        # 3. Aplicar ratio
        ratio = real_total / total_local_assigned
        
        for bot in bots:
            bot.current_balance = (bot.current_balance * ratio).quantize(Decimal("1.00000000"))
            bot.initial_balance = (bot.initial_balance * ratio).quantize(Decimal("1.00000000"))
            bot.save()
            
        messages.success(request, f"¡Sincronización exitosa! Balances ajustados proporcionalmente al saldo real (${real_total:.2f} USDT).")
        
    except Exception as e:
        messages.error(request, f"Error durante la sincronización: {e}")
        
    return redirect('bot_dashboard')

@login_required
def analyze_volatility_api(request):
    """API para obtener rangos sugeridos basados en volatilidad (ATR/BB)"""
    symbol = request.GET.get('symbol')
    if not symbol:
        return JsonResponse({'status': 'error', 'message': 'Missing symbol'}, status=400)
    
    from ..ccxttest1 import binance as exchange
    from ..indicadores import atr, bollinger_bands
    import pandas as pd
    
    try:
        # Fetch 1D para ATR
        ohlcv_1d = exchange.fetch_ohlcv(symbol, '1d', limit=20)
        df_1d = pd.DataFrame(ohlcv_1d, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df_1d['atr'] = atr(df_1d, 14)
        current_atr = float(df_1d['atr'].dropna().iloc[-1])
        
        # Fetch 4H para Bollinger
        ohlcv_4h = exchange.fetch_ohlcv(symbol, '4h', limit=30)
        df_4h = pd.DataFrame(ohlcv_4h, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df_4h = bollinger_bands(df_4h, window=20, num_std=2, generate_signals=False)
        current_upper = float(df_4h['bb_upper'].dropna().iloc[-1])
        current_lower = float(df_4h['bb_lower'].dropna().iloc[-1])
        current_close = float(df_4h['close'].iloc[-1])
        
        # Matemática automática para sugerir grid
        suggested_upper = current_upper * 1.01
        suggested_lower = current_lower * 0.99
        
        # Rango total
        grid_range = suggested_upper - suggested_lower
        
        # Distancia sugerida aprox 40% del ATR diario
        target_step = current_atr * 0.40
        if target_step <= 0: target_step = current_close * 0.01  # fallback 1%
        
        suggested_levels = int(grid_range / target_step)
        if suggested_levels < 3: suggested_levels = 3
        if suggested_levels > 50: suggested_levels = 50
        
        return JsonResponse({
            'status': 'success',
            'symbol': symbol,
            'current_price': round(current_close, 4),
            'atr_1d': round(current_atr, 4),
            'bb_upper_4h': round(current_upper, 4),
            'bb_lower_4h': round(current_lower, 4),
            'suggested_upper': round(suggested_upper, 4),
            'suggested_lower': round(suggested_lower, 4),
            'suggested_levels': suggested_levels
        })
        
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
@require_POST
def trigger_kill_switch(request):
    """Activa manualmente la parada de emergencia global."""
    try:
        from ..bot_manager import BotManager
        BotManager.emergency_stop_all(reason=f"MANUAL by {request.user.username}")
        messages.success(request, "¡KILL-SWITCH ACTIVADO! Todos los bots detenidos y posiciones liquidadas.")
    except Exception as e:
        messages.error(request, f"Error al activar Kill-Switch: {e}")
    return redirect('bot_dashboard')

@login_required
@require_POST
def update_risk_settings(request):
    """Actualiza los parámetros de riesgo global y Telegram."""
    try:
        max_dd = request.POST.get('max_drawdown_pct')
        reset_ks = request.POST.get('reset_kill_switch') == 'on'
        
        # Telegram fields
        telegram_token = request.POST.get('telegram_token')
        telegram_chat_id = request.POST.get('telegram_chat_id')
        notifications_enabled = request.POST.get('notifications_enabled') == 'on'
        
        settings, _ = GlobalSettings.objects.get_or_create(id=1)
        if max_dd:
            settings.max_drawdown_pct = Decimal(max_dd)
        
        if reset_ks:
            settings.kill_switch_active = False
            messages.success(request, "Kill-Switch desactivado. El sistema vuelve a operar.")
        
        # Update Telegram settings
        settings.telegram_token = telegram_token
        settings.telegram_chat_id = telegram_chat_id
        settings.notifications_enabled = notifications_enabled
        
        settings.save()
        messages.success(request, "Configuración guardada exitosamente.")
    except Exception as e:
        messages.error(request, f"Error al actualizar configuración: {e}")
    return redirect('bot_dashboard')

@login_required
@require_POST
def test_telegram_view(request):
    """Envía un mensaje de prueba a Telegram."""
    from ..utils.notifications import send_telegram_message
    success = send_telegram_message("🤖 <b>¡Conexión Exitosa!</b>\nTu bot de trading ahora está vinculado con esta cuenta de Telegram.")
    if success:
        messages.success(request, "Mensaje de prueba enviado. Revisa tu Telegram.")
    else:
        messages.error(request, "Error enviando mensaje. Verifica el Token y Chat ID.")
    return redirect('bot_dashboard')

