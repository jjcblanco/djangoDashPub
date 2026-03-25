from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.db import models
from django.db.models import Sum
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_POST
from ..models import LiveBot, LiveTrade, TradingPair, CapitalFunding, GlobalSettings, DailyMetric, WhaleWallet, WhaleTransaction, PatternInsight, ShadowTrade
from ..bot_manager import BotManager
from ..services import SolanaWhaleTracker, PatternEngine
import json
import requests
from dashboard.services import get_top_scored_whales
from dashboard.whale_scoring import WhaleScoringEngine
from dashboard.whale_analysis import WhaleAnalysisEngine

@login_required
def whale_insights(request):
    """Vista para seguimiento de ballenas y análisis de patrones."""
    from django.utils import timezone
    from django.db.models import Count
    top_whales = get_top_scored_whales(limit=5, min_trades=3)
    try:
        # Mostrar todas las billeteras con sus totales de datos para dimensionar
        wallets = WhaleWallet.objects.annotate(
            tx_count=Count('transactions', distinct=True),
            trade_count=Count('shadow_trades', distinct=True)
        ).order_by('-created_at')
        
        # Sincronizar billeteras si se solicita
        if request.GET.get('sync') == '1':
            try:
                with open('whale_debug.log', 'a') as f:
                    f.write(f"\n[{timezone.now()}] Iniciando Sincronización vía Web...\n")
            except: pass
            
            from dashboard.services import SolanaWhaleTracker, EVMWhaleTracker

            for wallet in wallets:
                try:
                    # Despacho por Red
                    if wallet.blockchain == 'solana':
                        tracker = SolanaWhaleTracker()
                        tracker.sync_wallet(wallet, max_new=2, signatures_limit=5)
                    elif wallet.blockchain in ['ethereum', 'base']:
                        tracker = EVMWhaleTracker(wallet.blockchain)
                        tracker.sync_wallet(wallet, max_new=5)
                    elif wallet.blockchain == 'hyperliquid':
                        from dashboard.services import HyperliquidWhaleTracker
                        tracker = HyperliquidWhaleTracker()
                        tracker.sync_wallet(wallet, max_new=10)
                    
                    PatternEngine.analyze_wallet(wallet)
                except Exception as e:
                    try:
                        with open('whale_debug.log', 'a') as f:
                            f.write(f"Error sincronizando {wallet.address[:8]} ({wallet.blockchain}): {e}\n")
                    except: pass
            
            messages.success(request, "Billeteras sincronizadas y analizadas correctamente.")
            return redirect('whale_insights')

        insights = PatternInsight.objects.all().order_by('-detected_at')[:20]
        
        # Calcular P&L para cada billetera
        for wallet in wallets:
            wallet.pnl_stats = PatternEngine.get_wallet_pnl(wallet)
            score_data = WhaleScoringEngine.calculate_score(wallet)
            wallet.score_data = score_data
            
        # Operaciones Shadow Activas
        from ..models import ShadowTrade
        from dashboard.services import fetch_current_price
        shadow_trades = ShadowTrade.objects.filter(status='OPEN').order_by('-created_at')
        
        # Calcular PnL en tiempo real para cada shadow trade
        for trade in shadow_trades:
            current_price = fetch_current_price(trade.token_symbol)
            if current_price and trade.entry_price and float(trade.entry_price) > 0:
                trade.current_price = current_price
                trade.live_pnl = round(((current_price - float(trade.entry_price)) / float(trade.entry_price)) * 100, 2)
            else:
                trade.current_price = None
                trade.live_pnl = None
        
        # Tokens Hot (Tendencias)
        hot_tokens = PatternEngine.get_hot_tokens(hours=24)
            
        context = {
            'wallets': wallets,
            'insights': insights,
            'shadow_trades': shadow_trades,
            'hot_tokens': hot_tokens,
            'page_title': 'Whale Insights & Alpha',
            'top_scored_whales': top_whales,
        }
        return render(request, 'dashboard/whale_insights.html', context)
    except Exception as e:
        import traceback
        error_msg = traceback.format_exc()
        try:
            with open('whale_debug.log', 'a') as f:
                f.write(f"\n--- {timezone.now()} ---\n{error_msg}\n")
        except:
            pass
        return HttpResponse(f"<h3>Error 500 en Whale Insights</h3><pre>{error_msg}</pre>", status=500)

@login_required
@require_POST
def follow_whale(request):
    """Añade una nueva billetera a la lista de seguimiento."""
    try:
        address = request.POST.get('address')
        name = request.POST.get('name')
        blockchain = request.POST.get('blockchain', 'solana')
        
        # Normalizar dirección
        if address:
            address = address.strip()
            # EVM chains are case-insensitive
            if blockchain in ['ethereum', 'base']:
                address = address.lower()
        
        if not address:
            messages.error(request, "La dirección es obligatoria.")
            return redirect('whale_insights')
            
        # Evitar duplicados (ahora permite la misma dirección en distintas redes)
        if WhaleWallet.objects.filter(address=address, blockchain=blockchain).exists():
            messages.warning(request, f"La billetera {address} ya está siendo seguida en la red {blockchain.upper()}.")
            return redirect('whale_insights')
            
        WhaleWallet.objects.create(
            address=address,
            name=name,
            blockchain=blockchain,
            wallet_category=request.POST.get('wallet_category', 'OBSERVATION'),
            filter_mode=request.POST.get('filter_mode', 'OPEN'),
            target_token=request.POST.get('target_token', ''),
            is_active=True
        )
        messages.success(request, f"Ahora sigues a {name or address[:8]}.")
        
    except Exception as e:
        messages.error(request, f"Error al seguir billetera: {e}")
        
    return redirect('whale_insights')

@login_required
def bot_dashboard(request):
    """Vista principal para gestionar bots con diagnóstico."""
    import logging
    logger = logging.getLogger(__name__)
    
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

    except Exception as e:
        import traceback
        from django.http import HttpResponse
        return HttpResponse(f"<h3>Error 500 en Dashboard (Etapa Datos)</h3><pre>{traceback.format_exc()}</pre>", status=500)

    try:
        # Calcular capital total inyectado (histórico)
        total_injected_capital = CapitalFunding.objects.aggregate(total=models.Sum('amount'))['total'] or Decimal("0")
        funding_history = CapitalFunding.objects.all().order_by('-funding_date')[:10]
        
        # Calcular Beneficio Real Absoluto (Saldo Actual - Capital Inyectado)
        real_net_profit = Decimal("0")
        if exchange_balance:
            real_net_profit = real_total - total_injected_capital

        # 7. Gráfico de Equidad (Equity Curve)
        metrics = DailyMetric.objects.all().order_by('date')
        
        if not metrics.exists():
            logger.info("No existen métricas de rendimiento. Intentando generar snapshot inicial...")
            try:
                from ..utils.performance import snapshot_daily_metrics
                success, error_msg = snapshot_daily_metrics()
                if success:
                    metrics = DailyMetric.objects.all().order_by('date')
                    logger.info("Snapshot inicial generado con éxito.")
                else:
                    logger.error(f"Fallo al generar snapshot inicial de métricas: {error_msg}")
                    messages.warning(request, f"Aviso: No se pudo obtener el saldo de Binance para el gráfico de hoy. (Error: {error_msg})")
            except Exception as e:
                logger.error(f"Error forzando snapshot inicial: {e}")

        equity_chart = None
        if metrics.exists():
            logger.info(f"Generando gráfico con {metrics.count()} puntos de datos.")
            try:
                import plotly.graph_objs as go
                from plotly.offline import plot
                
                # Tomar los últimos 30 días para no saturar
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
                    title={
                        'text': 'Evolución del Capital (Equity Curve)',
                        'y':0.9,
                        'x':0.5,
                        'xanchor': 'center',
                        'yanchor': 'top',
                        'font': {'size': 18, 'color': '#5a5c69'}
                    },
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
                logger.info("Gráfico generado correctamente y enviado al contexto.")
            except Exception as e:
                logger.error(f"Error generando gráfico de equidad: {e}")
                messages.error(request, f"Error técnico generando gráfico: {str(e)[:50]}")
        else:
            logger.warning("No hay datos suficientes para mostrar el gráfico de equidad.")

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
        from django.http import HttpResponse
        return HttpResponse(f"<h3>Error 500 en Dashboard (Etapa Render)</h3><pre>{traceback.format_exc()}</pre>", status=500)

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
        
        # Notificación Telegram
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
        
        # Balance inicial y actual (opcional)
        balance = request.POST.get('balance')
        if balance:
            bot.initial_balance = Decimal(balance)
            bot.current_balance = Decimal(balance)
            
        # Extraer parámetros dinámicos según estrategia
        params = bot.parameters.copy()
        
        # Parámetros comunes
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

        # Verificar si es necesario resetear trades (si cambian parámetros críticos de GRID)
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
            # Cancelar trades en espera para que el manager haga bootstrap en el siguiente ciclo
            zombie_trades = LiveTrade.objects.filter(bot=bot, status='WAITING')
            zombie_count = zombie_trades.count()
            zombie_trades.update(status='CANCELED')
            messages.info(request, f"Se han cancelado {zombie_count} órdenes pendientes para reiniciar la grilla con los nuevos parámetros.")
        
        # Permitir cambiar entre Live/Paper
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
            send_telegram_message(f"⏹️ <b>Bot Detenido</b>\nEl bot <code>{bot.name}</code> ({bot.pair.symbol}) se ha detenido manualmente.")
            
        elif action == 'close_only':
            bot.status = 'CLOSE_ONLY'
            bot.save()
            messages.info(request, f"Bot '{bot.name}' en modo SOLO CIERRE (Se venderá lo abierto, no se comprará más).")
            send_telegram_message(f"⚠️ <b>Modo Solo Cierre</b>\nEl bot <code>{bot.name}</code> ha sido puesto en modo de reducción.")
            
        elif action == 'clear_error':
            bot.last_error = None
            bot.status = 'STOPPED'
            bot.save()
            messages.success(request, f"Error de '{bot.name}' limpiado. Estado reseteado a STOPPED.")
            
        elif action == 'delete':
            bot_name = bot.name
            bot_pair = bot.pair.symbol
            bot.delete()
            messages.success(request, "Bot eliminado.")
            send_telegram_message(f"🗑️ <b>Bot Eliminado</b>\nEl bot <code>{bot_name}</code> ({bot_pair}) ha sido removido del sistema.")
            
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
    """Envía un mensaje de prueba a Telegram usando credenciales capturadas o guardadas."""
    from ..utils.notifications import send_telegram_message
    
    # Intentar obtener del POST (para probar antes de guardar) o de la DB
    token = request.POST.get('telegram_token')
    chat_id = request.POST.get('telegram_chat_id')
    
    success = send_telegram_message(
        "🤖 <b>¡Conexión Exitosa!</b>\nTu bot de trading ahora está vinculado con esta cuenta de Telegram.",
        token_override=token,
        chat_id_override=chat_id,
        force=True
    )
    
    if success:
        messages.success(request, "Mensaje de prueba enviado. Revisa tu Telegram.")
    else:
        messages.error(request, "Error enviando mensaje. Verifica el Token y Chat ID.")
    return redirect('bot_dashboard')



@login_required
def bot_detail(request, bot_id):
    """Vista de analisis detallado para un bot especifico."""
    import plotly.graph_objs as go
    import plotly.offline as pyo
    from collections import defaultdict

    bot = get_object_or_404(LiveBot, id=bot_id)
    all_trades = list(LiveTrade.objects.filter(bot=bot).order_or_404("entry_time"))
    closed_trades = [t for t in all_trades if t.status in ("CLOSED", "CLOSED_EMERGENCY") and t.pnl is not None]
    open_trades = [t for t in all_trades if t.status == "OPEN"]

    # ---- METRICAS BASICAS ----
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

    # ---- DURACION PROMEDIO ----
    durations = [
        (t.exit_time - t.entry_time).total_seconds() / 3600
        for t in closed_trades if t.exit_time and t.entry_time
    ]
    avg_duration_h = (sum(durations) / len(durations)) if durations else 0

    # ---- STREAKS ----
    max_win_streak = max_loss_streak = cur_win = cur_loss = 0
    for t in closed_trades:
        if float(t.pnl) > 0:
            cur_win += 1; cur_loss = 0
        else:
            cur_loss += 1; cur_win = 0
        max_win_streak  = max(max_win_streak,  cur_win)
        max_loss_streak = max(max_loss_streak, cur_loss)

    # ---- EQUITY CURVE + MAX DRAWDOWN ----
    balance = float(bot.initial_balance)
    peak = balance
    max_drawdown = 0
    eq_times, eq_values = [], []
    for t in closed_trades:
        balance += float(t.pnl)
        eq_times.append(t.exit_time)
        eq_values.append(balance)
        if balance > peak:
            peak = balance
        dd = (peak - balance) / peak * 100 if peak > 0 else 0
        if dd > max_drawdown:
            max_drawdown = dd

    # ---- GRAFICO: EQUITY CURVE ----
    equity_chart = ""
    if eq_values:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=eq_times, y=eq_values, mode="lines+markers", name="Balance",
            line=dict(color="#2ecc71", width=2), marker=dict(size=4),
            fill="tozeroy", fillcolor="rgba(46,204,113,0.1)"
        ))
        fig.add_hline(y=float(bot.initial_balance), line_dash="dash",
                      line_color="rgba(255,255,255,0.35)", annotation_text="Capital inicial")
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#ecf0f1"), height=300,
            margin=dict(l=50, r=20, t=20, b=40),
            xaxis=dict(gridcolor="rgba(255,255,255,0.1)"),
            yaxis=dict(gridcolor="rgba(255,255,255,0.1)", tickprefix="$"),
            showlegend=False
        )
        equity_chart = pyo.plot(fig, output_type="div", include_plotlyjs=False)

    # ---- GRAFICO: PnL DIARIO ----
    pnl_by_day = defaultdict(float)
    for t in closed_trades:
        if t.exit_time:
            pnl_by_day[t.exit_time.date()] += float(t.pnl)

    pnl_daily_chart = ""
    if pnl_by_day:
        days = sorted(pnl_by_day.keys())
        vals = [pnl_by_day[d] for d in days]
        fig2 = go.Figure(go.Bar(
            x=days, y=vals,
            marker_color=["#2ecc71" if v >= 0 else "#e74c3c" for v in vals]
        ))
        fig2.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#ecf0f1"), height=240,
            margin=dict(l=50, r=20, t=10, b=40),
            xaxis=dict(gridcolor="rgba(255,255,255,0.1)"),
            yaxis=dict(gridcolor="rgba(255,255,255,0.1)", tickprefix="$"),
            showlegend=False
        )
        pnl_daily_chart = pyo.plot(fig2, output_type="div", include_plotlyjs=False)

    context = {
        "bot": bot,
        "total_trades": total_trades,
        "win_rate": round(win_rate, 2),
        "total_pnl": round(total_pnl, 4),
        "roi": round(roi, 2),
        "profit_factor": round(profit_factor_val, 2) if profit_factor_val is not None else "Inf",
        "gross_profit": round(gross_profit, 4),
        "gross_loss": round(gross_loss, 4),
        "avg_win": round(avg_win, 4),
        "avg_loss": round(avg_loss, 4),
        "max_drawdown": round(max_drawdown, 2),
        "max_win_streak": max_win_streak,
        "max_loss_streak": max_loss_streak,
        "avg_duration_h": round(avg_duration_h, 2),
        "winning_count": len(winning),
        "losing_count": len(losing),
        "equity_chart": equity_chart,
        "pnl_daily_chart": pnl_daily_chart,
        "closed_trades": list(reversed(closed_trades)),
        "open_trades": open_trades,
    }
    return render(request, "dashboard/bot_detail.html", context)

@login_required
@require_POST
def unfollow_whale(request, wallet_id):
    """Deja de seguir a una billetera (eliminación física)."""
    try:
        from ..models import WhaleWallet
        wallet = get_object_or_404(WhaleWallet, id=wallet_id)
        name = wallet.name or wallet.address[:8]
        # Eliminamos la billetera (Cascade eliminará transacciones e insights)
        wallet.delete()
        messages.success(request, f"Has dejado de seguir a {name} correctamente.")
    except Exception as e:
        messages.error(request, f"Error al dejar de seguir: {e}")
        
    return redirect('whale_insights')

@login_required
@require_POST
def simulate_whale_trade(request):
    """Simula una copia de trade de ballena (Shadow Trading)."""
    try:
        from ..models import ShadowTrade, WhaleWallet
        wallet_id = request.POST.get('wallet_id')
        symbol = request.POST.get('symbol', 'SOL')
        mint = request.POST.get('mint', '')
        # Un precio ficticio para la simulación inicial si no viene por POST
        price_val = request.POST.get('price', '0')
        entry_price = Decimal(price_val) if price_val else Decimal('0')
        
        amount_val = request.POST.get('amount', '1')
        amount = Decimal(amount_val) if amount_val else Decimal('1')
        
        wallet = get_object_or_404(WhaleWallet, id=wallet_id)
        
        ShadowTrade.objects.create(
            wallet=wallet,
            token_symbol=symbol,
            token_mint=mint,
            entry_price=entry_price,
            amount=amount,
            status='OPEN'
        )
        messages.success(request, f"¡Simulación de copia en {symbol} abierta correctamente!")
    except Exception as e:
        messages.error(request, f"Error al abrir simulación: {e}")
        
    return redirect('whale_insights')

@login_required
@require_POST
def close_shadow_trade(request, trade_id):
    """Cierra una operación de Shadow Trading y calcula el P&L final."""
    try:
        from ..models import ShadowTrade
        from django.utils import timezone
        trade = get_object_or_404(ShadowTrade, id=trade_id)
        
        # Obtener precio real de mercado
        exit_val = request.POST.get('exit_price')
        if exit_val:
            exit_price = Decimal(exit_val)
        else:
            # Consultar precio actual en tiempo real
            from dashboard.services import fetch_current_price
            real_price = fetch_current_price(trade.token_symbol)
            if real_price:
                exit_price = Decimal(str(real_price))
            else:
                # Fallback: usar entry_price (PnL = 0%) si no se puede obtener precio
                exit_price = trade.entry_price
        
        trade.exit_price = exit_price
        trade.status = 'CLOSED'
        trade.closed_at = timezone.now()
        
        # Calcular P&L %
        trade.pnl_percent = float((trade.exit_price - trade.entry_price) / trade.entry_price * 100)
        trade.save()
        
        messages.success(request, f"Simulación de {trade.token_symbol} cerrada con {trade.pnl_percent:.2f}% de P&L.")
    except Exception as e:
        messages.error(request, f"Error al cerrar simulación: {e}")
        
    return redirect('whale_insights')

@login_required
def search_tokens_ajax(request):
    """Proxy para buscar tokens en DexScreener API."""
    query = request.GET.get('q', '')
    if len(query) < 2:
        return JsonResponse({'results': []})
        
    url = f"https://api.dexscreener.com/latest/dex/search?q={query}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    try:
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            pairs = data.get('pairs', [])
            
            # Formatear resultados
            results = []
            seen_mints = set() # Evitar duplicados por diferentes pools
            
            for p in pairs:
                mint = p.get('baseToken', {}).get('address')
                if not mint or mint in seen_mints: continue
                
                results.append({
                    'name': p.get('baseToken', {}).get('name'),
                    'symbol': p.get('baseToken', {}).get('symbol'),
                    'pairName': f"{p.get('baseToken', {}).get('symbol')}/{p.get('quoteToken', {}).get('symbol')}",
                    'price': p.get('priceUsd'),
                    'liquidity': p.get('liquidity', {}).get('usd'),
                    'fdv': p.get('fdv'),
                    'mint': mint,
                    'url': p.get('url'),
                    'chain': p.get('chainId')
                })
                seen_mints.add(mint)
                if len(results) >= 10: break
                
            return JsonResponse({'results': results})
        return JsonResponse({'error': 'Error en DexScreener API'}, status=500)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
@login_required
def get_whale_history(request, wallet_id):
    """Retorna el historial de transacciones de una billetera en formato JSON."""
    wallet = get_object_or_404(WhaleWallet, id=wallet_id)
    transactions = wallet.transactions.all().order_by('-timestamp')[:50]
    
    data = []
    for tx in transactions:
        # Formatear assets para que no salgan nulos
        if wallet.blockchain == 'solana':
            from_asset = tx.from_asset or "???"
            to_asset = tx.to_asset or "???"
            # En Solana a veces el "type" es UNKNOWN hasta que PatternEngine lo procesa
            tx_type = tx.tx_type
        else:
            # En EVM ya vienen limpios del tracker
            from_asset = tx.from_asset
            to_asset = tx.to_asset
            tx_type = tx.tx_type

        mkt_ctx = tx.raw_data.get('market_context', {}) if isinstance(tx.raw_data, dict) else {}
        
        data.append({
            'id': tx.id,
            'timestamp': tx.timestamp.strftime('%Y-%m-%d %H:%M'),
            'type': tx_type,
            'from_asset': from_asset,
            'to_asset': to_asset,
            'amount_in': float(tx.amount_in) if tx.amount_in else 0,
            'amount_out': float(tx.amount_out) if tx.amount_out else 0,
            'tx_hash': tx.tx_hash,
            'market_context': mkt_ctx,
            'explorer_url': f"https://solscan.io/tx/{tx.tx_hash}" if wallet.blockchain == 'solana' else (
                f"https://etherscan.io/tx/{tx.tx_hash.split('_')[0]}" if wallet.blockchain == 'ethereum' else 
                (f"https://basescan.org/tx/{tx.tx_hash.split('_')[0]}" if wallet.blockchain == 'base' else 
                 f"https://app.hyperliquid.xyz/explorer/address/{wallet.address}") # HL explorer por ahora a la dirección
            )
        })
    
    return JsonResponse({
        'status': 'success',
        'wallet_name': wallet.name or wallet.address[:8],
        'blockchain': wallet.blockchain,
        'transactions': data
    })

@login_required
def export_whale_history(request, wallet_id):
    """Exporta el historial de transacciones de una billetera a un archivo CSV."""
    import csv
    wallet = get_object_or_404(WhaleWallet, id=wallet_id)
    transactions = wallet.transactions.all().order_by('-timestamp')
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="whale_{wallet.address[:8]}_history.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Timestamp', 'Type', 'From Asset', 'To Asset', 'Amount In', 'Amount Out', 'TX Hash',
        'RSI_14', 'MACD', 'MACD_Signal', 'Price_vs_SMA50', 'Price_vs_SMA200', 'BB_Position', 'Vol_Ratio', 'Uptrend'
    ])
    
    for tx in transactions:
        mkt_ctx = tx.raw_data.get('market_context', {}) if isinstance(tx.raw_data, dict) else {}
        
        writer.writerow([
            tx.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            tx.tx_type,
            tx.from_asset,
            tx.to_asset,
            tx.amount_in,
            tx.amount_out,
            tx.tx_hash,
            mkt_ctx.get('rsi_14', ''),
            mkt_ctx.get('macd', ''),
            mkt_ctx.get('macd_signal', ''),
            mkt_ctx.get('price_vs_sma50', ''),
            mkt_ctx.get('price_vs_sma200', ''),
            mkt_ctx.get('bb_position', ''),
            mkt_ctx.get('volume_ratio', ''),
            mkt_ctx.get('in_uptrend', '')
        ])
    
    return response

@login_required
def trigger_deep_sync(request, wallet_id):
    """Ejecuta una sincronización profunda para una billetera (especialmente Hyperliquid)."""
    wallet = get_object_or_404(WhaleWallet, id=wallet_id)
    
    from dashboard.services import SolanaWhaleTracker, EVMWhaleTracker, HyperliquidWhaleTracker, PatternEngine
    
    try:
        new_txs = 0
        if wallet.blockchain == 'solana':
            tracker = SolanaWhaleTracker()
            new_txs = tracker.sync_wallet(wallet, max_new=100, signatures_limit=200)
        elif wallet.blockchain in ['ethereum', 'base']:
            tracker = EVMWhaleTracker(wallet.blockchain)
            new_txs = tracker.sync_wallet(wallet, max_new=100)
        elif wallet.blockchain == 'hyperliquid':
            tracker = HyperliquidWhaleTracker()
            new_txs = tracker.sync_wallet(wallet, max_new=500)
            
        PatternEngine.analyze_wallet(wallet)
        
        return JsonResponse({
            'status': 'success',
            'new_transactions': new_txs,
            'message': f"Sincronizados {new_txs} movimientos nuevos."
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
def get_whale_insights(request, wallet_id):
    """Retorna insights avanzados de éxito para una ballena con reporte de errores."""
    import traceback
    try:
        wallet = get_object_or_404(WhaleWallet, id=wallet_id)
        
        # Obtener análisis de correlación
        analysis = WhaleAnalysisEngine.analyze_success_correlation(wallet_id=wallet.id)
        
        if not analysis or 'error' in analysis:
            return JsonResponse({
                'status': 'error', 
                'message': analysis.get('error', 'Datos insuficientes para generar insights.') if analysis else 'Datos insuficientes.'
            })
            
        return JsonResponse({
            'status': 'success',
            'analysis': analysis
        })
    except Exception as e:
        error_msg = traceback.format_exc()
        return JsonResponse({
            'status': 'error',
            'message': f"Internal error: {str(e)}",
            'debug_info': error_msg
        }, status=500)
