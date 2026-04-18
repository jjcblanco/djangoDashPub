"""
scalping_views.py
=================
Vistas para el módulo de scalping: dashboard, API endpoints, y gestión de bots.
"""
import json
import logging
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.utils import timezone
from django.db.models import Avg, Sum, Count

from dashboard.models import (
    ScalpingBot, ScalpingTrade, ScalpAlert, PairScanResult, Pair,
)
from dashboard.tasks import (
    scan_scalping_pairs_task,
    run_scalping_bot_task,
)

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# DASHBOARD PRINCIPAL
# ──────────────────────────────────────────────────────────────

@login_required
def scalping_dashboard(request):
    """Vista principal del módulo de scalping."""
    # Top pares del último scan
    latest_scan_time = PairScanResult.objects.values('scanned_at').order_by('-scanned_at').first()
    if latest_scan_time:
        top_pairs = PairScanResult.objects.filter(
            scanned_at__gte=latest_scan_time['scanned_at']
        ).order_by('-total_score')[:15]
    else:
        top_pairs = PairScanResult.objects.none()

    # Alertas activas (últimas 2 horas, no expiradas)
    active_alerts = ScalpAlert.objects.filter(
        is_active=True,
        created_at__gte=timezone.now() - timezone.timedelta(hours=2),
    ).select_related('pair').order_by('-confidence', '-created_at')[:20]

    # Mis bots
    bots = ScalpingBot.objects.all().select_related('pair').order_by('-created_at')

    # Estadísticas globales de scalping
    global_stats = ScalpingTrade.objects.aggregate(
        total_trades  = Count('id'),
        total_pnl     = Sum('pnl_usdt'),
        avg_pnl_pct   = Avg('pnl_pct'),
        wins          = Count('id', filter=__import__('django.db.models', fromlist=['Q']).Q(pnl_usdt__gt=0)),
    )

    # Trades recientes (últimas 24h)
    recent_trades = ScalpingTrade.objects.filter(
        entry_time__gte=timezone.now() - timezone.timedelta(hours=24)
    ).select_related('bot', 'bot__pair').order_by('-entry_time')[:20]

    context = {
        'top_pairs':     top_pairs,
        'active_alerts': active_alerts,
        'bots':          bots,
        'recent_trades': recent_trades,
        'global_stats':  global_stats,
        'last_scan':     latest_scan_time['scanned_at'] if latest_scan_time else None,
        'strategy_choices': ScalpingBot.STRATEGY_CHOICES,
        'timeframe_choices': ScalpingBot.TIMEFRAME_CHOICES,
        'pairs_available': Pair.objects.filter(exchange='binance').order_by('symbol'),
    }
    return render(request, 'dashboard/scalping_dashboard.html', context)


# ──────────────────────────────────────────────────────────────
# API ENDPOINTS (polling del frontend)
# ──────────────────────────────────────────────────────────────

@login_required
@require_GET
def scalping_api_alerts(request):
    """Devuelve las alertas activas en JSON para polling del frontend."""
    since_minutes = int(request.GET.get('minutes', 60))
    alerts = ScalpAlert.objects.filter(
        is_active=True,
        created_at__gte=timezone.now() - timezone.timedelta(minutes=since_minutes),
    ).select_related('pair').order_by('-confidence', '-created_at')[:30]

    data = []
    for a in alerts:
        data.append({
            'id':           a.id,
            'pair':         a.pair.symbol,
            'timeframe':    a.timeframe,
            'strategy':     a.strategy,
            'signal':       a.signal_type,
            'price':        float(a.price_at_alert),
            'sl':           float(a.suggested_sl) if a.suggested_sl else None,
            'tp':           float(a.suggested_tp) if a.suggested_tp else None,
            'confidence':   round(a.confidence * 100, 1),
            'created_at':   a.created_at.strftime('%H:%M:%S'),
            'expires_at':   a.expires_at.strftime('%H:%M:%S') if a.expires_at else None,
        })
    return JsonResponse({'alerts': data, 'count': len(data)})


@login_required
@require_GET
def scalping_api_scan_results(request):
    """Devuelve el último scan de pares en JSON."""
    latest = PairScanResult.objects.values('scanned_at').order_by('-scanned_at').first()
    if not latest:
        return JsonResponse({'pairs': [], 'scanned_at': None})

    results = PairScanResult.objects.filter(
        scanned_at__gte=latest['scanned_at']
    ).select_related('pair').order_by('-total_score')[:15]

    data = []
    for r in results:
        signals = r.signals_found or []
        best_signal = signals[0] if signals else None
        data.append({
            'symbol':               r.pair.symbol,
            'price':                float(r.current_price) if r.current_price else None,
            'total_score':          round(r.total_score, 1),
            'volatility_score':     round(r.volatility_score, 1),
            'volume_score':         round(r.volume_score, 1),
            'trend_score':          round(r.trend_score, 1),
            'signal_score':         round(r.signal_score, 1),
            'atr_pct':              round(r.atr_pct, 3) if r.atr_pct else None,
            'volume_24h_usdt':      r.volume_24h_usdt,
            'adx_value':            round(r.adx_value, 1) if r.adx_value else None,
            'recommended_strategy': r.recommended_strategy,
            'signals_count':        len(signals),
            'best_signal':          best_signal,
        })

    return JsonResponse({
        'pairs': data,
        'scanned_at': latest['scanned_at'].strftime('%H:%M:%S'),
        'count': len(data),
    })


@login_required
@require_GET
def scalping_api_bot_stats(request):
    """Estadísticas en tiempo real de los bots de scalping."""
    bots = ScalpingBot.objects.all().select_related('pair')
    data = []
    for bot in bots:
        open_trade = ScalpingTrade.objects.filter(bot=bot, status='OPEN').first()
        data.append({
            'id':            bot.id,
            'name':          bot.name,
            'pair':          bot.pair.symbol,
            'strategy':      bot.get_strategy_type_display(),
            'timeframe':     bot.timeframe,
            'status':        bot.status,
            'is_live':       bot.is_live,
            'total_trades':  bot.total_trades,
            'win_rate':      bot.win_rate,
            'total_pnl':     float(bot.total_pnl_usdt),
            'capital_usdt':  float(bot.capital_usdt),
            'open_trade':    {
                'side':  open_trade.side,
                'entry': float(open_trade.entry_price),
                'sl':    float(open_trade.stop_loss),
                'tp':    float(open_trade.take_profit),
            } if open_trade else None,
        })
    return JsonResponse({'bots': data})


# ──────────────────────────────────────────────────────────────
# GESTIÓN DE BOTS
# ──────────────────────────────────────────────────────────────

@login_required
@require_POST
def scalping_create_bot(request):
    """Crea un nuevo ScalpingBot."""
    try:
        data = json.loads(request.body)

        pair_symbol = data.get('pair', '').upper()
        pair_obj, _ = Pair.objects.get_or_create(
            symbol=pair_symbol,
            defaults={
                'base_asset':  pair_symbol.split('/')[0] if '/' in pair_symbol else pair_symbol,
                'quote_asset': pair_symbol.split('/')[1] if '/' in pair_symbol else 'USDT',
                'exchange':    'binance',
            }
        )

        bot = ScalpingBot.objects.create(
            name             = data.get('name', f'Scalp {pair_symbol}'),
            pair             = pair_obj,
            strategy_type    = data.get('strategy_type', 'EMA_CROSS'),
            timeframe        = data.get('timeframe', '5m'),
            is_live          = data.get('is_live', False),
            capital_usdt     = data.get('capital_usdt', 100),
            max_position_pct = data.get('max_position_pct', 50),
            sl_atr_mult      = data.get('sl_atr_mult', 1.5),
            tp_atr_mult      = data.get('tp_atr_mult', 2.5),
            parameters       = data.get('parameters', {}),
        )

        return JsonResponse({
            'success': True,
            'bot_id':  bot.id,
            'message': f'Bot "{bot.name}" creado en modo {"LIVE" if bot.is_live else "SIMULADO"}.',
        })

    except Exception as e:
        logger.error(f'[ScalpViews] Error creando bot: {e}')
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
@require_POST
def scalping_bot_action(request, bot_id):
    """Acciones sobre un bot: start, pause, stop, toggle_live."""
    bot = get_object_or_404(ScalpingBot, id=bot_id)
    try:
        data   = json.loads(request.body)
        action = data.get('action')

        if action == 'start':
            bot.status = 'RUNNING'
            bot.last_error = None
            bot.save(update_fields=['status', 'last_error'])
            return JsonResponse({'success': True, 'status': 'RUNNING'})

        elif action == 'pause':
            bot.status = 'PAUSED'
            bot.save(update_fields=['status'])
            return JsonResponse({'success': True, 'status': 'PAUSED'})

        elif action == 'stop':
            bot.status = 'STOPPED'
            bot.save(update_fields=['status'])
            return JsonResponse({'success': True, 'status': 'STOPPED'})

        elif action == 'toggle_live':
            # Solo permitir activar live si el bot tiene historial simulado positivo
            if not bot.is_live:
                if bot.total_trades < 5:
                    return JsonResponse({
                        'success': False,
                        'error': 'Necesitas al menos 5 trades simulados antes de activar modo LIVE.'
                    }, status=400)
                if bot.win_rate < 50:
                    return JsonResponse({
                        'success': False,
                        'error': f'Win rate ({bot.win_rate}%) insuficiente para modo LIVE. Necesitas >50%.'
                    }, status=400)
            bot.is_live = not bot.is_live
            bot.save(update_fields=['is_live'])
            mode = 'LIVE' if bot.is_live else 'SIMULADO'
            return JsonResponse({'success': True, 'is_live': bot.is_live, 'message': f'Bot en modo {mode}'})

        elif action == 'delete':
            bot.delete()
            return JsonResponse({'success': True, 'message': 'Bot eliminado.'})

        elif action == 'run_now':
            # Ejecutar el bot sincrónicamente una vez (útil si no hay Celery Beat)
            from dashboard.tasks import run_scalping_bot_task
            try:
                run_scalping_bot_task(bot.id)  # llamada directa, no .delay()
                return JsonResponse({'success': True, 'message': 'Bot ejecutado. Revisá los trades para ver si hubo señal.'})
            except Exception as run_err:
                return JsonResponse({'success': False, 'error': str(run_err)}, status=500)

        return JsonResponse({'success': False, 'error': 'Acción desconocida.'}, status=400)

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_POST
def scalping_dismiss_alert(request, alert_id):
    """Desestima una alerta del feed."""
    alert = get_object_or_404(ScalpAlert, id=alert_id)
    alert.is_active = False
    alert.save(update_fields=['is_active'])
    return JsonResponse({'success': True})


# ──────────────────────────────────────────────────────────────
# ACCIONES MANUALES
# ──────────────────────────────────────────────────────────────

@login_required
@require_POST
def scalping_trigger_scan(request):
    """
    Dispara un escaneo manual de pares.
    Si el body incluye sync=true, ejecuta sincrónicamente y devuelve los resultados
    directamente en el JSON para que el frontend pueda actualizar la tabla al instante.
    """
    try:
        data      = json.loads(request.body) if request.body else {}
        timeframe = data.get('timeframe', '5m')
        sync_mode = data.get('sync', False)

        if sync_mode:
            # ── Modo sincrónico: ejecutar en esta request y devolver resultados ──
            from dashboard.pair_scanner import scan_all_pairs, save_scan_results
            logger.info(f'[ScalpScan] Escaneo sincrónico {timeframe} iniciado...')
            results = scan_all_pairs(timeframe=timeframe, top_n=15, run_signals=True)
            if results:
                save_scan_results(results, timeframe=timeframe)

            pairs_data = []
            for r in results:
                signals   = r.get('signals_found', [])
                best_sig  = signals[0] if signals else None
                pairs_data.append({
                    'symbol':               r['symbol'],
                    'price':                r['price'],
                    'total_score':          round(r['total_score'], 1),
                    'volatility_score':     round(r['volatility_score'], 1),
                    'volume_score':         round(r['volume_score'], 1),
                    'trend_score':          round(r['trend_score'], 1),
                    'signal_score':         round(r['signal_score'], 1),
                    'atr_pct':              round(r['atr_pct'], 3) if r.get('atr_pct') else None,
                    'adx_value':            round(r['adx_value'], 1) if r.get('adx_value') else None,
                    'recommended_strategy': r.get('recommended_strategy'),
                    'signals_count':        len(signals),
                    'best_signal':          best_sig,
                })

            return JsonResponse({
                'success':    True,
                'sync':       True,
                'pairs':      pairs_data,
                'scanned_at': timezone.now().strftime('%H:%M:%S'),
                'count':      len(pairs_data),
            })
        else:
            # ── Modo asíncrono: delegar a Celery (para el beat automático) ──
            scan_scalping_pairs_task.delay(timeframe=timeframe, top_n=15)
            return JsonResponse({'success': True, 'sync': False, 'message': f'Escaneo {timeframe} iniciado en background.'})

    except Exception as e:
        logger.error(f'[ScalpScan] Error en escaneo: {e}')
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_POST
def scalping_close_trade(request, trade_id):
    """Cierra manualmente un ScalpingTrade abierto."""
    trade = get_object_or_404(ScalpingTrade, id=trade_id)
    if trade.status != 'OPEN':
        return JsonResponse({'success': False, 'error': 'El trade no está abierto.'}, status=400)

    try:
        price = None
        if trade.bot.is_live:
            from dashboard.pair_scanner import _get_exchange
            exchange = _get_exchange()
            if exchange:
                symbol    = trade.bot.pair.symbol
                side_close= 'sell' if trade.side == 'BUY' else 'buy'
                order     = exchange.create_market_order(symbol, side_close, float(trade.quantity))
                price     = float(order.get('price') or order.get('average') or 0)
                trade.exit_order_id = str(order.get('id', ''))

        if not price:
            # Precio simulado: usar el actual
            from dashboard.pair_scanner import _get_exchange
            exchange = _get_exchange()
            if exchange:
                ticker = exchange.fetch_ticker(trade.bot.pair.symbol)
                price  = float(ticker.get('last', 0))

        if not price:
            return JsonResponse({'success': False, 'error': 'No se pudo obtener precio de cierre.'}, status=500)

        ep  = float(trade.entry_price)
        qty = float(trade.quantity)
        pnl_usdt = (price - ep) * qty if trade.side == 'BUY' else (ep - price) * qty
        pnl_pct  = (pnl_usdt / (ep * qty)) * 100 if ep * qty > 0 else 0

        trade.exit_price = price
        trade.exit_time  = timezone.now()
        trade.status     = 'CLOSED_MANUAL'
        trade.pnl_usdt   = round(pnl_usdt, 4)
        trade.pnl_pct    = round(pnl_pct, 4)
        trade.save()

        # Actualizar bot stats
        bot = trade.bot
        bot.total_pnl_usdt += pnl_usdt
        if pnl_usdt > 0:
            bot.winning_trades += 1
        bot.save(update_fields=['total_pnl_usdt', 'winning_trades'])

        return JsonResponse({'success': True, 'pnl_usdt': float(trade.pnl_usdt), 'exit_price': price})

    except Exception as e:
        logger.error(f'[ScalpViews] Error cerrando trade {trade_id}: {e}')
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
