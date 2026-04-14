from decimal import Decimal
import json
import requests
from django.db.models import Count, Q
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.core.cache import cache
import logging
logger = logging.getLogger(__name__)

from ..models import WhaleWallet, WhaleTransaction, PatternInsight, TradingPair, ShadowTrade, WhalePattern
from ..services import SolanaWhaleTracker, PatternEngine
from ..whale_pattern_learner import WhalePatternLearner
from dashboard.services import get_top_scored_whales
from dashboard.whale_scoring import WhaleScoringEngine
from dashboard.whale_analysis import WhaleAnalysisEngine
from dashboard.data_service import generar_grafico_desde_señales, DataManager
from dashboard.indicadores import calculate_rsi, macd
from ..ccxttest1 import _ensure_binance_initialized, binance
from .utils import ajax_rate_limit

@login_required
def whale_insights(request):
    """Vista para seguimiento de ballenas y análisis de patrones."""
    try:
        top_whales = []

        # ── Filtro por par ──────────────────────────────────────────────
        active_pair = request.GET.get('pair', '').strip().upper()

        # Calcular lista dinámica de pares disponibles desde target_pairs de todas las wallets
        all_pair_values = WhaleWallet.objects.exclude(
            target_pairs__isnull=True
        ).exclude(target_pairs='').values_list('target_pairs', flat=True)

        available_pairs = set()
        for raw in all_pair_values:
            for token in raw.split(','):
                t = token.strip().upper()
                if t:
                    available_pairs.add(t)
        available_pairs = sorted(available_pairs)

        # ── Wallets: filtrar por par si está activo ─────────────────────
        wallets_qs = WhaleWallet.objects.annotate(
            tx_count=Count('transactions', distinct=True),
            trade_count=Count('shadow_trades', distinct=True)
        ).order_by('-created_at')

        if active_pair:
            wallets_qs = wallets_qs.filter(target_pairs__icontains=active_pair)
        
        wallets = wallets_qs[:50]

        # ── Sincronización masiva ───────────────────────────────────────
        if request.GET.get('sync') == '1':
            from dashboard.tasks import sync_all_whales_task
            try:
                sync_all_whales_task.delay()
                messages.success(request, "Sincronización masiva iniciada en segundo plano.")
            except Exception as e:
                messages.error(request, f"Error al encolar tarea de sincronización: {e}. ¿Está corriendo Redis/Celery?")
            return redirect('whale_insights')

        # ── Insights ────────────────────────────────────────────────────
        insights_qs = PatternInsight.objects.all().order_by('-detected_at')
        if active_pair:
            insights_qs = insights_qs.filter(
                meta_data__hot_token_symbol__iexact=active_pair
            )
        insights = insights_qs[:20]

        # ── Whale Patterns (Learned) ────────────────────────────────────
        patterns_qs = WhalePattern.objects.filter(is_active=True).order_by('-avg_pnl')
        if active_pair:
            # Filter patterns that mention this pair in conditions or name
            patterns_qs = patterns_qs.filter(
                Q(conditions__contains=active_pair) |
                Q(pattern_name__icontains=active_pair)
            )
        patterns = patterns_qs[:20]

        # ── PnL por wallet (desde caché) ────────────────────────────────
        for wallet in wallets:
            cache_key = f"wallet_score_{wallet.id}"
            cached_data = cache.get(cache_key)
            if cached_data:
                wallet.pnl_stats = cached_data.get('pnl')
                wallet.score_data = cached_data.get('score')
            else:
                wallet.pnl_stats = {'total_pnl': 0, 'win_rate': 0, 'status': 'Cargando...'}
                wallet.score_data = {'score': 0, 'tier': 'Calculando...', 'category': {'name': 'Pendiente', 'color': 'gray'}}

        # ── Shadow Trades: filtrar por par ──────────────────────────────
        shadow_qs = ShadowTrade.objects.filter(status='OPEN').order_by('-created_at')
        if active_pair:
            shadow_qs = shadow_qs.filter(token_symbol__iexact=active_pair)
        shadow_trades = shadow_qs

        for trade in shadow_trades:
            trade.current_price = None
            trade.live_pnl = None

        hot_tokens = []

        context = {
            'wallets': wallets,
            'insights': insights,
            'patterns': patterns,
            'shadow_trades': shadow_trades,
            'hot_tokens': hot_tokens,
            'page_title': 'Whale Insights & Alpha',
            'top_scored_whales': top_whales,
            'pairs': TradingPair.objects.all(),
            # filtro por par
            'available_pairs': available_pairs,
            'active_pair': active_pair,
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
        return HttpResponse(f"<h3>Error (Capturado) en Whale Insights</h3><pre>{error_msg}</pre>", status=200)

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
            if blockchain in ['ethereum', 'base']:
                address = address.lower()
        
        if not address:
            messages.error(request, "La dirección es obligatoria.")
            return redirect('whale_insights')
            
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
@require_POST
def unfollow_whale(request, wallet_id):
    """Deja de seguir a una billetera (eliminación física)."""
    try:
        wallet = get_object_or_404(WhaleWallet, id=wallet_id)
        name = wallet.name or wallet.address[:8]
        wallet.delete()
        messages.success(request, f"Has dejado de seguir a {name} correctamente.")
    except Exception as e:
        messages.error(request, f"Error al dejar de seguir: {e}")
        
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
            
            results = []
            seen_mints = set()
            
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
        if wallet.blockchain == 'solana':
            from_asset = tx.from_asset or "???"
            to_asset = tx.to_asset or "???"
            tx_type = tx.tx_type
        else:
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
                 f"https://app.hyperliquid.xyz/explorer/address/{wallet.address}")
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
    from dashboard.tasks import sync_wallet_task
    
    try:
        sync_wallet_task.delay(wallet.id, deep_sync=True)
        return JsonResponse({
            'status': 'success',
            'new_transactions': 0,
            'message': f"Sincronización profunda iniciada en segundo plano para {wallet.name or wallet.address[:8]}."
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
def get_whale_insights(request, wallet_id):
    """Retorna insights avanzados de éxito para una ballena con reporte de errores."""
    import traceback
    try:
        wallet = get_object_or_404(WhaleWallet, id=wallet_id)
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

@login_required
@ajax_rate_limit(max_calls=10, period_seconds=60)
def discover_contract_whales_ajax(request):
    """
    Busca las billeteras más activas para un contrato de token específico.
    Parte de la herramienta Whale Scout.
    """
    address = request.GET.get('address')
    blockchain = request.GET.get('blockchain', 'ethereum')
    
    if not address or len(address) < 30:
        return JsonResponse({'status': 'error', 'message': 'Dirección de contrato válida requerida.'}, status=400)
    
    try:
        whales = PatternEngine.discover_token_whales(address.strip(), blockchain)
        
        if not whales:
            return JsonResponse({'status': 'error', 'message': 'No se encontraron movimientos significativos recientemente.'})
            
        return JsonResponse({
            'status': 'success',
            'whales': whales,
            'token_symbol': whales[0].get('symbol', 'TOKEN') if whales else 'TOKEN'
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
@ajax_rate_limit(max_calls=30, period_seconds=60)
def whale_scores_ajax(request):
    """Retorna scores y PnL de todas las billeteras seguidas. Llamado vía AJAX post-pageload."""
    wallets = WhaleWallet.objects.all().values('id', 'name', 'address')
    result = []
    
    for w in wallets:
        cache_key = f"wallet_score_{w['id']}"
        cached = cache.get(cache_key)
        
        if not cached:
            wallet_obj = WhaleWallet.objects.get(id=w['id'])
            try:
                pnl = PatternEngine.get_wallet_pnl(wallet_obj)
            except Exception:
                pnl = {'roi': 0, 'status': 'neutral', 'pnl_usdt': 0}
            try:
                score = WhaleScoringEngine.calculate_score(wallet_obj)
            except Exception:
                score = {'score': 0, 'category': {'name': 'Sin datos', 'color': 'gray'}}
            cached = {'pnl': pnl, 'score': score}
            cache.set(cache_key, cached, 60 * 15)
        
        wallet_obj = WhaleWallet.objects.get(id=w['id'])
        result.append({
            'wallet_id': w['id'],
            'pnl': cached.get('pnl'),
            'score': cached.get('score'),
            'sync_status': wallet_obj.sync_status,
            'last_sync': wallet_obj.last_sync.strftime("%d/%m %H:%M") if wallet_obj.last_sync else "Nunca",
            'top_tokens': wallet_obj.top_tokens or {},
            'dna': wallet_obj.trading_dna or {},
        })
    
    return JsonResponse({'status': 'ok', 'wallets': result})

@login_required
@ajax_rate_limit(max_calls=30, period_seconds=60)
def whale_hot_tokens_ajax(request):
    """Retorna los tokens calientes. Llamado vía AJAX post-pageload."""
    hot_tokens = cache.get("hot_tokens_24h")
    if not hot_tokens:
        try:
            hot_tokens = PatternEngine.get_hot_tokens(hours=24)
            cache.set("hot_tokens_24h", hot_tokens, 60 * 15)
        except Exception:
            hot_tokens = []
    
    return JsonResponse({'status': 'ok', 'hot_tokens': hot_tokens})

@login_required
@ajax_rate_limit(max_calls=20, period_seconds=60)
def suggest_bot_from_whale(request, wallet_id):
    """
    Analiza el historial de una ballena y sugiere parámetros para crear un bot.
    Devuelve JSON con parámetros sugeridos para GRID y DayTrading.
    """
    token_symbol = request.GET.get('token', None)
    
    try:
        wallet = WhaleWallet.objects.get(id=wallet_id)
        result = WhaleAnalysisEngine.suggest_bot_params(wallet_id, token_symbol=token_symbol)
        
        if 'error' in result:
            return JsonResponse({'status': 'error', 'message': result['error']})
        
        name_token = result.get('top_token', token_symbol or 'TOKEN')
        result['suggested_name'] = f"Whale Bot - {wallet.name or wallet.address[:8]} ({name_token})"
        result['wallet_name'] = wallet.name or wallet.address[:12]
        
        return JsonResponse({'status': 'ok', 'data': result})
    except WhaleWallet.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Billetera no encontrada'}, status=404)
    except Exception as e:
        import traceback
        return JsonResponse({'status': 'error', 'message': str(e), 'trace': traceback.format_exc()}, status=500)


@login_required
def trigger_whale_hunt(request):
    """
    Lanza la tarea de caza de ballenas por pares.
    Siempre ejecuta de forma síncrona para dar feedback inmediato al usuario.
    """
    from dashboard.tasks import hunt_whales_by_pair_task

    # Primero verificar si hay targets activos
    from dashboard.models import WhaleHuntTarget
    target_count = WhaleHuntTarget.objects.filter(is_active=True).count()
    if target_count == 0:
        return JsonResponse({
            'status': 'warning',
            'message': '⚠️ No hay contratos activos en Hunt Targets. Agrega al menos uno en el panel de abajo.',
        })

    # Ejecutar síncronamente para dar feedback real al usuario
    try:
        result = hunt_whales_by_pair_task()
        new_count = result.get('new', 0) if isinstance(result, dict) else 0
        updated_count = result.get('updated', 0) if isinstance(result, dict) else 0
        buyers_found = result.get('total_buyers_found', 0) if isinstance(result, dict) else 0
        already_existed = result.get('already_existed', 0) if isinstance(result, dict) else 0
        filtered_by_vol = result.get('filtered_by_vol', 0) if isinstance(result, dict) else 0
        errors = result.get('errors', []) if isinstance(result, dict) else []
        scanned = result.get('scanned', 0) if isinstance(result, dict) else 0

        # Construir mensaje de feedback detallado
        if new_count > 0:
            msg = f'✅ Caza completada: {new_count} ballenas nuevas añadidas'
            if updated_count > 0:
                msg += f', {updated_count} actualizadas'
            msg += f'. ({buyers_found} compradores analizados en {scanned} tokens)'
            return JsonResponse({
                'status': 'success',
                'message': msg,
                'new_wallets': new_count,
                'updated_wallets': updated_count,
            })

        # No se encontraron wallets nuevas — dar feedback útil
        if buyers_found == 0:
            # La API no devolvió compradores
            error_detail = ' | '.join(errors[:3]) if errors else 'Las APIs no devolvieron datos de trades.'
            msg = (
                f'⚠️ Escaneo completo en {scanned} tokens, pero no se encontraron compradores. '
                f'Detalle: {error_detail}'
            )
        elif filtered_by_vol > 0 and already_existed == 0:
            # Hay compradores pero todos fueron filtrados por volumen
            msg = (
                f'⚠️ Se encontraron {buyers_found} compradores en {scanned} tokens, '
                f'pero todos fueron filtrados por volumen mínimo. '
                f'💡 Tip: Baja el "Vol. mín. USD" en tus targets para capturar más traders.'
            )
        elif already_existed > 0:
            # Todos los compradores ya estaban guardados
            msg = (
                f'🔍 Escaneo completo: {buyers_found} compradores en {scanned} tokens. '
                f'{already_existed} ya estaban en seguimiento'
            )
            if filtered_by_vol > 0:
                msg += f', {filtered_by_vol} filtrados por volumen mín'
            if updated_count > 0:
                msg += f', {updated_count} actualizados con nuevo par'
            msg += '. No hay ballenas de estreno.'
        else:
            msg = (
                f'🔍 Escaneo completo en {scanned} tokens. '
                f'No se encontraron ballenas nuevas.'
            )
            if errors:
                msg += f' Errores: {" | ".join(errors[:2])}'

        return JsonResponse({
            'status': 'warning',
            'message': msg,
        })
    except Exception as e:
        import traceback
        return JsonResponse({'status': 'error', 'message': f'Error ejecutando caza: {str(e)}'}, status=500)


# ─────────────────────────────────────────────────────────────
#  CRUD — WhaleHuntTarget (Gestión de contratos objetivo)
# ─────────────────────────────────────────────────────────────

@login_required
def hunt_targets_list(request):
    """Devuelve la lista actual de targets en JSON (para el panel AJAX)."""
    from ..models import WhaleHuntTarget
    targets = list(WhaleHuntTarget.objects.values(
        'id', 'token_symbol', 'blockchain', 'contract_address',
        'min_volume_usd', 'is_active', 'notes', 'created_at'
    ))
    # Formatear fecha
    for t in targets:
        t['created_at'] = t['created_at'].strftime('%d/%m/%Y') if t['created_at'] else ''
    return JsonResponse({'status': 'ok', 'targets': targets})


@login_required
@require_POST
def hunt_targets_add(request):
    """Crea un nuevo WhaleHuntTarget desde el formulario del panel."""
    from ..models import WhaleHuntTarget
    try:
        symbol    = request.POST.get('token_symbol', '').strip().upper()
        blockchain = request.POST.get('blockchain', 'ethereum').strip()
        contract  = request.POST.get('contract_address', '').strip()
        min_vol   = float(request.POST.get('min_volume_usd', 3000) or 3000)
        notes     = request.POST.get('notes', '').strip()

        if not symbol or not contract:
            return JsonResponse({'status': 'error', 'message': 'Símbolo y contrato son obligatorios.'}, status=400)

        if len(contract) < 20:
            return JsonResponse({'status': 'error', 'message': 'El contrato parece demasiado corto.'}, status=400)

        # Normalizar EVM
        if blockchain in ['ethereum', 'base']:
            contract = contract.lower()

        obj, created = WhaleHuntTarget.objects.get_or_create(
            contract_address=contract,
            blockchain=blockchain,
            defaults={
                'token_symbol': symbol,
                'min_volume_usd': min_vol,
                'notes': notes,
                'is_active': True,
            }
        )
        if not created:
            return JsonResponse({'status': 'error', 'message': f'El contrato ya existe para {blockchain.upper()}.'}, status=400)

        return JsonResponse({
            'status': 'ok',
            'message': f'✅ ${symbol} añadido a los targets de caza.',
            'target': {
                'id': obj.id, 'token_symbol': obj.token_symbol,
                'blockchain': obj.blockchain, 'contract_address': obj.contract_address,
                'min_volume_usd': obj.min_volume_usd, 'is_active': obj.is_active,
                'notes': obj.notes or '', 'created_at': obj.created_at.strftime('%d/%m/%Y'),
            }
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@login_required
@require_POST
def hunt_targets_toggle(request, target_id):
    """Activa o pausa un WhaleHuntTarget."""
    from ..models import WhaleHuntTarget
    try:
        target = get_object_or_404(WhaleHuntTarget, id=target_id)
        target.is_active = not target.is_active
        target.save(update_fields=['is_active'])
        estado = 'activado' if target.is_active else 'pausado'
        return JsonResponse({'status': 'ok', 'is_active': target.is_active, 'message': f'${target.token_symbol} {estado}.'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@login_required
@require_POST
def hunt_targets_delete(request, target_id):
    """Elimina un WhaleHuntTarget."""
    from ..models import WhaleHuntTarget
    try:
        target = get_object_or_404(WhaleHuntTarget, id=target_id)
        symbol = target.token_symbol
        target.delete()
        return JsonResponse({'status': 'ok', 'message': f'${symbol} eliminado de los targets.'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@login_required
def whale_consensus_ajax(request):
    """
    Devuelve las señales de consenso activas en JSON para el panel del dashboard.
    """
    from ..models import ConsensusSignal
    from django.utils import timezone

    signals = ConsensusSignal.objects.filter(
        status='ACTIVE',
    ).order_by('-detected_at')[:10]

    data = []
    for s in signals:
        # Calcular cambio de precio en vivo si tenemos precio de entrada
        price_change_pct = s.price_change_pct
        current_price = None
        if s.entry_price:
            try:
                from dashboard.services import fetch_current_price
                live_price = fetch_current_price(s.token_symbol)
                if live_price:
                    current_price = live_price
                    price_change_pct = round(
                        ((live_price - float(s.entry_price)) / float(s.entry_price)) * 100, 2
                    )
            except Exception:
                pass

        data.append({
            'id': s.id,
            'token_symbol': s.token_symbol,
            'blockchain': s.blockchain,
            'whale_count': s.whale_count,
            'confidence': s.confidence,
            'entry_price': float(s.entry_price) if s.entry_price else None,
            'current_price': current_price,
            'price_change_pct': price_change_pct,
            'detected_at': s.detected_at.strftime('%d/%m %H:%M'),
            'expires_at': s.expires_at.strftime('%d/%m %H:%M') if s.expires_at else None,
            'whale_addresses': s.whale_addresses,
        })

    return JsonResponse({'status': 'ok', 'signals': data})


@login_required
def whale_trade_chart_ajax(request, wallet_id):
    """
    Devuelve datos para el gráfico de operaciones de una ballena en un token:
    - price_data: precio histórico de GeckoTerminal (línea de fondo)
    - trades: lista de compras/ventas de la ballena superpuestas
    """
    import requests as req
    import plotly.graph_objects as go
    import pandas as pd
    from datetime import datetime
    from django.db.models import Q
    from dashboard.models import WhaleWallet, WhaleTransaction

    token = request.GET.get('token', '').upper().strip()
    wallet = get_object_or_404(WhaleWallet, id=wallet_id)
    blockchain = wallet.blockchain

    try:
        # 1. Determinar el Token a graficar
        if not token:
            token = wallet.target_pairs_list[0] if wallet.target_pairs_list else None
        if not token:
            any_tx = WhaleTransaction.objects.filter(wallet=wallet).first()
            if any_tx:
                token = any_tx.to_asset or any_tx.from_asset or 'TOKEN'
            else:
                return JsonResponse({'status': 'no_trades', 'message': 'Esta billetera no tiene transacciones todavía.'})

        # 2. Intentar obtener datos de Binance primero (para tokens comunes)
        ohlcv_df = pd.DataFrame()
        pool_address = None
        source = 'DEX'

        try:
            _ensure_binance_initialized()
            binance_symbol = f"{token}/USDT"
            
            if binance_symbol in binance.markets:
                logger.info(f"[WhaleChart] Token {token} encontrado en Binance. Usando CEX data.")
                # Obtener datos de Binance (DataManager maneja caché y DB)
                ohlcv_df = DataManager.get_or_fetch(
                    binance_symbol, 
                    timeframe='1h', # Usamos 1h para mejor detalle en tokens comunes
                    limit=1000
                )
                if not ohlcv_df.empty:
                    source = 'BINANCE'
                    # Normalizar columnas de DataManager si es necesario (ya deberían estar bien)
        except Exception as e:
            logger.error(f"[WhaleChart] Error consultando Binance: {e}")

        # 3. Fallback a DEX (DexScreener + GeckoTerminal) si Binance no tiene el token
        if ohlcv_df.empty:
            # Mapeo de redes para DexScreener y GeckoTerminal
            network_mapping = {
                'solana': 'solana',
                'ethereum': 'ethereum',
                'base': 'base',
                'hyperliquid': 'hyperliquid',
                'arbitrum': 'arbitrum',
                'bsc': 'bsc',
                'polygon': 'polygon',
                'optimism': 'optimism'
            }
            
            target_network = network_mapping.get(blockchain, 'ethereum')
            gecko_net = 'eth' if blockchain == 'ethereum' else target_network
            
            try:
                # Intentar buscar por símbolo o dirección
                dex_url = f"https://api.dexscreener.com/latest/dex/search?q={token}"
                dex_resp = req.get(dex_url, timeout=5)
                
                if dex_resp.status_code == 200:
                    pairs = dex_resp.json().get('pairs', [])
                    
                    # Filtrar por la red correcta. Aceptamos variaciones comunes de ID.
                    network_variants = [target_network, blockchain]
                    if target_network == 'ethereum': network_variants.append('eth')
                    
                    valid_pairs = [p for p in pairs if str(p.get('chainId')).lower() in network_variants]
                    
                    if valid_pairs:
                        # Ordenar por liquidez USD descendente para pillar el pool principal
                        valid_pairs.sort(key=lambda x: float(x.get('liquidity', {}).get('usd', 0)), reverse=True)
                        pool_address = valid_pairs[0].get('pairAddress')
                        
                        # Si el token era una dirección, ahora podemos usar su símbolo real para el título
                        if len(token) > 20: 
                            token = valid_pairs[0].get('baseToken', {}).get('symbol', token)
                
                if pool_address:
                    ohlcv_url = f"https://api.geckoterminal.com/api/v2/networks/{gecko_net}/pools/{pool_address}/ohlcv/day"
                    gecko_resp = req.get(ohlcv_url, timeout=5)
                    if gecko_resp.status_code == 200:
                        ohlcv_raw = gecko_resp.json().get('data', {}).get('attributes', {}).get('ohlcv_list', [])
                        if ohlcv_raw:
                            ohlcv_df = pd.DataFrame(ohlcv_raw, columns=['ts', 'open', 'high', 'low', 'close', 'vol'])
                            ohlcv_df['timestamp'] = pd.to_datetime(ohlcv_df['ts'], unit='s')
                            ohlcv_df = ohlcv_df.sort_values('timestamp')
            except Exception as e:
                logger.error(f"[WhaleChart] Error en fallback DEX: {e}")

        # 4. Obtener Operaciones de la Ballena
        txs = WhaleTransaction.objects.filter(wallet=wallet).filter(
            Q(to_asset__iexact=token) | Q(from_asset__iexact=token)
        ).order_by('timestamp')

        trades = []
        for tx in txs:
            trade_type = 'BUY'
            if tx.from_asset and tx.from_asset.upper() == token: trade_type = 'SELL'
            if tx.to_asset and tx.to_asset.upper() == token: trade_type = 'BUY'

            # Intentar extraer precio de raw_data
            price = None
            try:
                raw = tx.raw_data or {}
                p_val = raw.get('priceUsd') or raw.get('px') or raw.get('price') or 0
                price = float(p_val) if p_val else None
            except: pass

            trades.append({
                'timestamp': tx.timestamp.isoformat(),
                'date': tx.timestamp.strftime('%d/%m/%y %H:%M'),
                'type': trade_type,
                'price': price,
                'amount_in': float(tx.amount_in) if tx.amount_in else None,
                'amount_out': float(tx.amount_out) if tx.amount_out else None,
            })

        # 5. Calcular Indicadores Técnicos
        if not ohlcv_df.empty:
            if 'timestamp' not in ohlcv_df.columns and 'date' in ohlcv_df.columns:
                ohlcv_df = ohlcv_df.rename(columns={'date': 'timestamp'})
            
            ohlcv_df['ema9'] = ohlcv_df['close'].ewm(span=9, adjust=False).mean()
            ohlcv_df['ema21'] = ohlcv_df['close'].ewm(span=21, adjust=False).mean()
            ohlcv_df['ema50'] = ohlcv_df['close'].ewm(span=50, adjust=False).mean()
            ohlcv_df['ema200'] = ohlcv_df['close'].ewm(span=200, adjust=False).mean()
            ohlcv_df['rsi'] = calculate_rsi(ohlcv_df, period=14)
            ohlcv_df = macd(ohlcv_df)
        
        # 6. Preparar Operaciones para el Gráfico
        df_trades = pd.DataFrame(trades)
        final_df = ohlcv_df.copy()
        
        if not df_trades.empty and not ohlcv_df.empty:
            # Normalizar zonas horarias para evitar errores de merge (ambos a naive)
            df_trades['timestamp'] = pd.to_datetime(df_trades['timestamp'], utc=True).dt.tz_localize(None)
            ohlcv_df['timestamp'] = pd.to_datetime(ohlcv_df['timestamp'], utc=True).dt.tz_localize(None)
            
            # Mapear tipos para el gráfico
            df_trades['signal_type'] = df_trades['type'].map({'BUY': 'buy', 'SELL': 'sell'})
            
            # Asegurar que cada trade tenga un precio (si falta, usar el close más cercano)
            for i, row in df_trades.iterrows():
                if row['price'] is None:
                    # Buscar el precio de cierre más cercano en el tiempo
                    closest_idx = (ohlcv_df['timestamp'] - row['timestamp']).abs().idxmin()
                    df_trades.at[i, 'price'] = ohlcv_df.at[closest_idx, 'close']
            
            # Mezclar con el DF de precio para que Plotly los reconozca en la misma línea de tiempo
            # Usamos merge_asof para alinear trades con las velas horarias/diarias
            df_trades = df_trades.sort_values('timestamp')
            final_df = pd.merge_asof(
                ohlcv_df.sort_values('timestamp'),
                df_trades[['timestamp', 'signal_type', 'price']],
                on='timestamp',
                direction='nearest',
                tolerance=pd.Timedelta('1D') # Tolerancia amplia para modo diario
            )

        # 7. Generar Gráfico usando el servicio unificado
        viz_options = {
            'show_ema': True,
            'show_rsi': True,
            'show_macd': True,
            'show_ichimoku': False,
            'show_bb': False,
        }
        
        if not final_df.empty:
            chart_html = generar_grafico_desde_señales(final_df, token, viz_options=viz_options)
        else:
            chart_html = "<div class='alert alert-warning'>No hay datos de precio disponibles para este token.</div>"

        # Descubrir otros tokens disponibles para este whale (opcional para el selector)
        available_tokens = list(WhaleTransaction.objects.filter(wallet=wallet).values_list('to_asset', flat=True).distinct())
        available_tokens += list(WhaleTransaction.objects.filter(wallet=wallet).values_list('from_asset', flat=True).distinct())
        available_tokens = sorted(list(set([t.upper() for t in available_tokens if t and t.lower() != 'sol'])))

        return JsonResponse({
            'status': 'ok',
            'wallet_name': wallet.name or wallet.address[:12],
            'token': token,
            'available_tokens': available_tokens,
            'chart_html': chart_html,
            'trades': trades,
            'trade_count': len(trades),
        })

    except Exception as e:
        import traceback
        logger.error(f"Error Chart Ajax: {str(e)}\n{traceback.format_exc()}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@login_required
@require_POST
@ajax_rate_limit(max_calls=5, period_seconds=60)
def learn_patterns(request):
    """Ejecuta el aprendizaje de patrones a partir de trades cerrados."""
    try:
        # Llamar al learner
        patterns = WhalePatternLearner.analyze_trades(min_trades=1, min_win_rate=0.6)
        
        # Contar patrones activos en DB después del aprendizaje
        active_patterns = WhalePattern.objects.filter(is_active=True).count()
        
        return JsonResponse({
            'status': 'success',
            'message': f'Aprendizaje completado. {len(patterns)} patrones procesados.',
            'patterns_count': active_patterns,
        })
    except Exception as e:
        import traceback
        logger.error(f"Error en learn_patterns: {str(e)}\n{traceback.format_exc()}")
        return JsonResponse({
            'status': 'error',
            'message': f'Error interno: {str(e)}',
            'patterns_count': 0,
        }, status=500)
