from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.db import models
from django.db.models import Sum
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_POST
import json
import requests
import logging

from ..models import LiveBot, LiveTrade, TradingPair, CapitalFunding, GlobalSettings, DailyMetric, TradeSignal
from ..bot_manager import BotManager
from .utils import ajax_rate_limit

logger = logging.getLogger(__name__)

@login_required
def bot_dashboard(request):
    """Vista principal para gestionar bots con diagnóstico."""
    try:
        from ..ccxttest1 import binance as exchange
        
        bots = LiveBot.objects.all().order_by('-created_at')
        available_pairs = TradingPair.objects.filter(is_active=True)
        global_settings, _ = GlobalSettings.objects.get_or_create(id=1)
        
        bots_data = []
        for bot in bots:
            trades = LiveTrade.objects.filter(bot=bot)
            total_pnl = sum(t.pnl for t in trades)
            active_trades_query = trades.filter(status='OPEN')
            active_trades_count = active_trades_query.count()
            
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

        global_invested = sum(b.initial_balance for b in bots)
        global_assigned = sum(b.current_balance for b in bots)
        global_pnl = sum(d['total_pnl'] for d in bots_data)
        global_roi = (global_pnl / global_invested * 100) if global_invested > 0 else 0
        global_commission = LiveTrade.objects.aggregate(total=Sum('commission'))['total'] or Decimal("0")

        recent_trades = list(LiveTrade.objects.all().order_by('-entry_time')[:50])
        
        symbols = list(set([t.bot.pair.symbol for t in recent_trades if t.status == 'OPEN']))
        current_prices = {}
        if symbols:
            try:
                exchange.timeout = 5000
                tickers = exchange.fetch_tickers(symbols)
                current_prices = {s: tickers[s]['last'] for s in symbols if s in tickers}
            except Exception as e:
                logger.error(f"Error fetching tickers in dashboard: {e}")

        for trade in recent_trades:
            if trade.status == 'OPEN':
                symbol = trade.bot.pair.symbol
                trade.current_price = current_prices.get(symbol)
                
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
            if global_assigned > real_total + Decimal("1.0"):
                over_allocated = True
        except Exception as e:
            logger.error(f"Error fetching balance: {e}")

    except Exception as e:
        import traceback
        return HttpResponse(f"<h3>Error 500 en Dashboard (Etapa Datos)</h3><pre>{traceback.format_exc()}</pre>", status=500)

    try:
        total_injected_capital = CapitalFunding.objects.aggregate(total=models.Sum('amount'))['total'] or Decimal("0")
        funding_history = CapitalFunding.objects.all().order_by('-funding_date')[:10]
        
        real_net_profit = Decimal("0")
        if exchange_balance:
            real_net_profit = real_total - total_injected_capital

        metrics = DailyMetric.objects.all().order_by('date')
        
        if not metrics.exists():
            try:
                from ..utils.performance import snapshot_daily_metrics
                success, error_msg = snapshot_daily_metrics()
                if success:
                    metrics = DailyMetric.objects.all().order_by('date')
            except Exception as e:
                logger.error(f"Error forzando snapshot inicial: {e}")

        equity_chart = None
        if metrics.exists():
            try:
                import plotly.graph_objs as go
                from plotly.offline import plot
                
                recent_metrics = list(metrics)[-30:]
                dates = [m.date for m in recent_metrics]
                balances = [float(m.total_balance) for m in recent_metrics]
                
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=dates, 
                    y=balances, 
                    mode='lines+markers', 
                    name='Balance Total (USDT)',
                    line=dict(color='#4e73df', width=3),
                    marker=dict(size=8, color='#ffffff', line=dict(color='#4e73df', width=2)),
                    hovertemplate='<b>%{x}</b><br>Saldo: $%{y:,.2f}<extra></extra>'
                ))
                
                fig.update_layout(
                    title={'text': 'Evolución del Capital (Equity Curve)', 'y':0.9, 'x':0.5, 'xanchor': 'center', 'yanchor': 'top'},
                    xaxis_title=None,
                    yaxis_title='USDT',
                    template='plotly_white',
                    height=350,
                    margin=dict(l=40, r=40, t=60, b=40),
                    hovermode='x unified',
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    yaxis=dict(gridcolor='#f0f0f0', zerolinecolor='#f0f0f0')
                )
                equity_chart = plot(fig, output_type='div', include_plotlyjs='cdn')
            except Exception as e:
                logger.error(f"Error generando gráfico de equidad: {e}")
        
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
            'global_settings': global_settings,
            'equity_chart': equity_chart
        }
        return render(request, 'dashboard/bot_dashboard.html', context)
    except Exception as e:
        import traceback
        return HttpResponse(f"<h3>Error 500 en Dashboard (Etapa Render)</h3><pre>{traceback.format_exc()}</pre>", status=500)

@login_required
@require_POST
def add_funding(request):
    """Registra una nueva inyección de capital."""
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
                'strategy_mode': request.POST.get('strategy_mode', 'custom'),
                'min_strength': float(request.POST.get('min_strength', 3)),
                'min_adx': float(request.POST.get('min_adx', 20)),
                'allow_late_entry': request.POST.get('allow_late_entry') == 'on',
                'use_bollinger_filter': request.POST.get('use_bollinger_filter') == 'on',
                'use_candles': request.POST.get('use_candles') == 'on',
                'risk_per_trade_pct': float(request.POST.get('risk_per_trade_pct', 2.0)),
                'atr_sl': float(request.POST.get('atr_mult_sl', 1.5)),
                'atr_tp': float(request.POST.get('atr_mult_tp', 3.0)),
                'cooldown_bars': int(request.POST.get('cooldown_bars', 3))
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
        
        from ..utils.notifications import send_telegram_message
        msg = (
            f"🆕 <b>Bot Creado</b>\n"
            f"Nombre: <code>{name}</code>\n"
            f"Par: {pair.symbol}\n"
            f"Estrategia: {strategy_type}\n"
            f"Capital: ${balance}"
        )
        send_telegram_message(msg)
    except Exception as e:
        messages.error(request, f"Error al crear bot: {e}")
    
    return redirect('bot_dashboard')

@login_required
@require_POST
def edit_bot(request, bot_id):
    """Actualiza los parámetros de un bot existente."""
    try:
        bot = get_object_or_404(LiveBot, id=bot_id)
        name = request.POST.get('name')
        strategy_type = bot.strategy_type
        
        balance = request.POST.get('balance')
        if balance:
            bot.initial_balance = Decimal(balance)
            bot.current_balance = Decimal(balance)
            
        params = bot.parameters.copy()
        if request.POST.get('timeframe'):
            params['timeframe'] = request.POST.get('timeframe')
            
        if strategy_type == 'GRID':
            params.update({
                'upper_price': request.POST.get('upper_price'),
                'lower_price': request.POST.get('lower_price'),
                'grid_levels': request.POST.get('grid_levels'),
                'amount_per_level': request.POST.get('amount_per_level'),
                'global_stop_loss': request.POST.get('global_stop_loss'),
                'trailing_enabled': request.POST.get('trailing_enabled') == 'on',
                'trailing_down': request.POST.get('trailing_down') == 'on',
            })
        elif strategy_type == 'DAYTRADING':
            params.update({
                'strategy_mode': request.POST.get('strategy_mode', 'custom'),
                'min_strength': float(request.POST.get('min_strength', 3)),
                'min_adx': float(request.POST.get('min_adx', 20)),
                'allow_late_entry': request.POST.get('allow_late_entry') == 'on',
                'use_bollinger_filter': request.POST.get('use_bollinger_filter') == 'on',
                'use_candles': request.POST.get('use_candles') == 'on',
                'risk_per_trade_pct': float(request.POST.get('risk_per_trade_pct', 2.0)),
                'atr_sl': float(request.POST.get('atr_mult_sl', 1.5)),
                'atr_tp': float(request.POST.get('atr_mult_tp', 3.0)),
                'cooldown_bars': int(request.POST.get('cooldown_bars', 3))
            })

        needs_grid_reset = False
        if strategy_type == 'GRID':
            critical_keys = ['upper_price', 'lower_price', 'grid_levels']
            for key in critical_keys:
                if str(params.get(key)) != str(request.POST.get(key)):
                    needs_grid_reset = True
                    break
        
        bot.name = name
        bot.parameters = params
        
        if needs_grid_reset:
            zombie_trades = LiveTrade.objects.filter(bot=bot, status='WAITING')
            zombie_count = zombie_trades.count()
            zombie_trades.update(status='CANCELED')
            messages.info(request, f"Se han cancelado {zombie_count} órdenes pendientes.")
        
        bot.is_live = request.POST.get('is_live') == 'on'
        bot.save()
        messages.success(request, f"Parámetros de '{name}' actualizados correctamente.")
        
    except Exception as e:
        messages.error(request, f"Error al editar bot: {e}")
    
    return redirect('bot_dashboard')

@login_required
@require_POST
def bot_action(request, bot_id):
    """Controla el estado del bot (start/stop/delete)."""
    action = request.POST.get('action')
    try:
        bot = LiveBot.objects.get(id=bot_id)
        from ..utils.notifications import send_telegram_message
        
        if action == 'start':
            bot.status = 'RUNNING'
            bot.save()
            messages.success(request, f"Bot '{bot.name}' iniciado.")
            send_telegram_message(f"▶️ <b>Bot Iniciado</b>\nEl bot <code>{bot.name}</code> ({bot.pair.symbol}) ha comenzado a operar.")
            
        elif action == 'stop':
            bot.status = 'STOPPED'
            bot.save()
            messages.success(request, f"Bot '{bot.name}' detenido.")
            send_telegram_message(f"⏹️ <b>Bot Detenido</b>\nEl bot <code>{bot.name}</code> ({bot.pair.symbol}) se ha detenido.")
            
        elif action == 'close_only':
            bot.status = 'CLOSE_ONLY'
            bot.save()
            messages.info(request, f"Bot '{bot.name}' en modo SOLO CIERRE.")
            
        elif action == 'clear_error':
            bot.last_error = None
            bot.status = 'STOPPED'
            bot.save()
            messages.success(request, f"Error de '{bot.name}' limpiado.")
            
        elif action == 'delete':
            bot_name = bot.name
            bot.delete()
            messages.success(request, "Bot eliminado.")
            send_telegram_message(f"🗑️ <b>Bot Eliminado</b>\nEl bot <code>{bot_name}</code> ha sido removido.")
            
    except Exception as e:
        messages.error(request, f"Error: {e}")
        
    return redirect('bot_dashboard')

@login_required
@ajax_rate_limit(max_calls=10, period_seconds=60)
def trigger_bot_update(request):
    """Fuerza una actualización de todos los bots activos."""
    if not request.user.is_staff:
        return JsonResponse({'status': 'error', 'message': 'Permisos insuficientes'}, status=403)
        
    try:
        results = BotManager.update_all_active_bots()
        return JsonResponse({'status': 'ok', 'updated_count': len(results), 'results': results})
    except Exception as e:
        logger.error(f"ERROR en trigger_bot_update: {e}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
def trigger_balance_sync(request):
    """Sincroniza y recalibra los balances de los bots con el saldo real y parámetros."""
    if not request.user.is_staff:
        messages.error(request, "Acceso denegado.")
        return redirect('bot_dashboard')
        
    from ..ccxttest1 import binance as exchange
    try:
        # 1. Recalibración Contable (Lógica de recalibrate_bots.py)
        bots = LiveBot.objects.all()
        for bot in bots:
            # Sincronizar Capital Inicial si es GRID
            if bot.strategy_type == 'GRID':
                try:
                    levels = int(bot.parameters.get('grid_levels', 0))
                    amount = float(bot.parameters.get('amount_per_level', 0))
                    ideal = Decimal(str(levels * amount))
                    if bot.initial_balance < ideal:
                        bot.initial_balance = ideal
                except: pass
            
            # Recalcular saldo disponible (Initial + PnL - OpenCost)
            realized_pnl = LiveTrade.objects.filter(bot=bot).exclude(status__in=['OPEN', 'WAITING']).aggregate(total=Sum('pnl'))['total'] or Decimal("0")
            open_trades = LiveTrade.objects.filter(bot=bot, status__in=['OPEN', 'WAITING'])
            invested = sum(t.entry_price * t.amount for t in open_trades)
            
            new_current = bot.initial_balance + realized_pnl - invested
            bot.current_balance = max(new_current, Decimal("1.0")) # Evitar negativos
            bot.save()

        # 2. Sincronización Proporcional con Binance (Opcional - solo si hay fondos)
        try:
            bal = exchange.fetch_balance()
            real_total = Decimal(str(bal['total'].get('USDT', 0)))
            if real_total > 0:
                total_local = sum(b.current_balance for b in bots)
                if total_local > 0:
                    ratio = real_total / total_local
                    for b in bots:
                        b.current_balance = (b.current_balance * ratio).quantize(Decimal("1.00000000"))
                        b.save()
            messages.success(request, f"¡Sincronización y Recalibración completa! (${real_total:.2f} USDT detectados).")
        except Exception as e:
            messages.warning(request, f"Recalibración interna lista, pero falló la conexión con Binance: {e}")
            
    except Exception as e:
        messages.error(request, f"Error durante la sincronización: {e}")
    return redirect('bot_dashboard')

@login_required
def apply_strategic_optimizations(request):
    """Aplica parches tácticos a bots específicos por su nombre."""
    if not request.user.is_staff:
        messages.error(request, "Acceso denegado.")
        return redirect('bot_dashboard')
        
    results = []
    
    # 1. etcgrid - Mover rango y Trailing
    try:
        b = LiveBot.objects.get(name="etcgrid")
        p = b.parameters
        p['upper_price'] = '2150'
        p['lower_price'] = '1750'
        p['trailing_down'] = True
        b.parameters = p
        b.save()
        results.append("etcgrid: Rango ajustado 1750-2150 y Trailing Down ON.")
    except LiveBot.DoesNotExist: pass

    # 2. all time sol - Malla SOL real
    try:
        b = LiveBot.objects.get(name="all time sol")
        p = b.parameters
        if "SOL" in b.pair.symbol:
            p['upper_price'] = '145' # Ajustado a SOL real actual aprox
            p['lower_price'] = '115'
            results.append("all time sol: Rango SOL ajustado 115-145.")
        else:
            p['upper_price'] = '2200'
            p['lower_price'] = '1800'
            results.append("all time sol: Rango ETH ajustado 1800-2200.")
        b.parameters = p
        b.save()
    except LiveBot.DoesNotExist: pass

    # 3. ethdaynuevo - Daytrading filters
    try:
        b = LiveBot.objects.get(name="ethdaynuevo")
        p = b.parameters
        p['atr_sl'] = 2.0
        p['min_strength'] = 2.0
        b.parameters = p
        b.save()
        results.append("ethdaynuevo: ATR SL (2.0) y Strength (2.0) optimizados.")
    except LiveBot.DoesNotExist: pass

    if results:
        messages.success(request, "Optimizaciones aplicadas: " + " | ".join(results))
    else:
        messages.warning(request, "No se encontraron los bots específicos para optimizar por nombre.")
        
    return redirect('bot_dashboard')

@login_required
@ajax_rate_limit(max_calls=20, period_seconds=60)
def analyze_volatility_api(request):
    """API para obtener rangos sugeridos basados en volatilidad."""
    symbol = request.GET.get('symbol')
    if not symbol:
        return JsonResponse({'status': 'error', 'message': 'Missing symbol'}, status=400)
    
    from ..ccxttest1 import binance as exchange
    from ..indicadores import atr, bollinger_bands
    import pandas as pd
    
    try:
        ohlcv_1d = exchange.fetch_ohlcv(symbol, '1d', limit=20)
        df_1d = pd.DataFrame(ohlcv_1d, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df_1d['atr'] = atr(df_1d, 14)
        current_atr = float(df_1d['atr'].dropna().iloc[-1])
        
        ohlcv_4h = exchange.fetch_ohlcv(symbol, '4h', limit=30)
        df_4h = pd.DataFrame(ohlcv_4h, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df_4h = bollinger_bands(df_4h, window=20, num_std=2, generate_signals=False)
        current_upper = float(df_4h['bb_upper'].dropna().iloc[-1])
        current_lower = float(df_4h['bb_lower'].dropna().iloc[-1])
        current_close = float(df_4h['close'].iloc[-1])
        
        suggested_upper = current_upper * 1.01
        suggested_lower = current_lower * 0.99
        grid_range = suggested_upper - suggested_lower
        target_step = current_atr * 0.40
        if target_step <= 0: target_step = current_close * 0.01
        
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
    if not request.user.is_staff:
        messages.error(request, "Acceso denegado.")
        return redirect('bot_dashboard')
        
    try:
        BotManager.emergency_stop_all(reason=f"MANUAL by {request.user.username}")
        messages.success(request, "¡KILL-SWITCH ACTIVADO!")
    except Exception as e:
        messages.error(request, f"Error: {e}")
    return redirect('bot_dashboard')

@login_required
@require_POST
def update_risk_settings(request):
    """Actualiza los parámetros de riesgo global y Telegram."""
    if not request.user.is_staff:
        messages.error(request, "Acceso denegado.")
        return redirect('bot_dashboard')
        
    try:
        max_dd = request.POST.get('max_drawdown_pct')
        reset_ks = request.POST.get('reset_kill_switch') == 'on'
        settings, _ = GlobalSettings.objects.get_or_create(id=1)
        if max_dd: settings.max_drawdown_pct = Decimal(max_dd)
        if reset_ks: settings.kill_switch_active = False
        
        settings.telegram_token = request.POST.get('telegram_token')
        settings.telegram_chat_id = request.POST.get('telegram_chat_id')
        settings.notifications_enabled = request.POST.get('notifications_enabled') == 'on'
        settings.save()
        messages.success(request, "Configuración guardada exitosamente.")
    except Exception as e:
        messages.error(request, f"Error: {e}")
    return redirect('bot_dashboard')

@login_required
@require_POST
def test_telegram_view(request):
    """Envía un mensaje de prueba a Telegram."""
    from ..utils.notifications import send_telegram_message
    token = request.POST.get('telegram_token')
    chat_id = request.POST.get('telegram_chat_id')
    success = send_telegram_message("🤖 ¡Conexión Exitosa!", token_override=token, chat_id_override=chat_id, force=True)
    if success: messages.success(request, "Mensaje de prueba enviado.")
    else: messages.error(request, "Error enviando mensaje.")
    return redirect('bot_dashboard')

@login_required
def bot_detail(request, bot_id):
    """Análisis detallado de performance para un bot específico."""
    import plotly.graph_objs as go
    import plotly.offline as pyo
    from collections import defaultdict

    bot = get_object_or_404(LiveBot, id=bot_id)
    all_trades = list(LiveTrade.objects.filter(bot=bot).order_by("entry_time"))
    closed_trades = [t for t in all_trades if t.status in ("CLOSED", "CLOSED_EMERGENCY") and t.pnl is not None]
    open_trades = [t for t in all_trades if t.status == "OPEN"]

    total_trades = len(closed_trades)
    winning = [t for t in closed_trades if float(t.pnl) > 0]
    losing  = [t for t in closed_trades if float(t.pnl) <= 0]
    win_rate = (len(winning) / total_trades * 100) if total_trades > 0 else 0
    total_pnl = sum(float(t.pnl) for t in closed_trades)
    gross_profit = sum(float(t.pnl) for t in winning)
    gross_loss   = abs(sum(float(t.pnl) for t in losing))
    profit_factor_val = (gross_profit / gross_loss) if gross_loss > 0 else None
    avg_win  = (gross_profit / len(winning)) if winning else 0
    avg_loss = (gross_loss  / len(losing))  if losing  else 0
    roi = (total_pnl / float(bot.initial_balance) * 100) if bot.initial_balance > 0 else 0

    durations = [(t.exit_time - t.entry_time).total_seconds() / 3600 for t in closed_trades if t.exit_time and t.entry_time]
    avg_duration_h = (sum(durations) / len(durations)) if durations else 0

    max_win_streak = max_loss_streak = cur_win = cur_loss = 0
    for t in closed_trades:
        if float(t.pnl) > 0: cur_win += 1; cur_loss = 0
        else: cur_loss += 1; cur_win = 0
        max_win_streak  = max(max_win_streak,  cur_win)
        max_loss_streak = max(max_loss_streak, cur_loss)

    balance = float(bot.initial_balance)
    peak = balance
    max_drawdown = 0
    eq_times, eq_values = [], []
    for t in closed_trades:
        balance += float(t.pnl)
        eq_times.append(t.exit_time)
        eq_values.append(balance)
        if balance > peak: peak = balance
        dd = (peak - balance) / peak * 100 if peak > 0 else 0
        if dd > max_drawdown: max_drawdown = dd

    equity_chart = ""
    if eq_values:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=eq_times, y=eq_values, mode="lines+markers", name="Balance", line=dict(color="#2ecc71", width=2), fill="tozeroy", fillcolor="rgba(46,204,113,0.1)"))
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#ecf0f1"), height=300, yaxis=dict(tickprefix="$"), showlegend=False)
        equity_chart = pyo.plot(fig, output_type="div", include_plotlyjs=False)

    pnl_by_day = defaultdict(float)
    for t in closed_trades:
        if t.exit_time: pnl_by_day[t.exit_time.date()] += float(t.pnl)

    pnl_daily_chart = ""
    if pnl_by_day:
        days = sorted(pnl_by_day.keys())
        vals = [pnl_by_day[d] for d in days]
        fig2 = go.Figure(go.Bar(x=days, y=vals, marker_color=["#2ecc71" if v >= 0 else "#e74c3c" for v in vals]))
        fig2.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#ecf0f1"), height=240, showlegend=False)
        pnl_daily_chart = pyo.plot(fig2, output_type="div", include_plotlyjs=False)

    context = {
        "bot": bot, "total_trades": total_trades, "win_rate": round(win_rate, 2), "total_pnl": round(total_pnl, 4), "roi": round(roi, 2),
        "profit_factor": round(profit_factor_val, 2) if profit_factor_val is not None else "Inf", "gross_profit": round(gross_profit, 4),
        "gross_loss": round(gross_loss, 4), "avg_win": round(avg_win, 4), "avg_loss": round(avg_loss, 4), "max_drawdown": round(max_drawdown, 2),
        "max_win_streak": max_win_streak, "max_loss_streak": max_loss_streak, "avg_duration_h": round(avg_duration_h, 2),
        "winning_count": len(winning), "losing_count": len(losing), "equity_chart": equity_chart, "pnl_daily_chart": pnl_daily_chart,
        "closed_trades": list(reversed(closed_trades)), "open_trades": open_trades,
    }
    return render(request, "dashboard/bot_detail.html", context)
