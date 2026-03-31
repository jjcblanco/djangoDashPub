from decimal import Decimal
import json
import requests
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_POST
from django.db.models import Count
from django.utils import timezone
from django.core.cache import cache

from ..models import WhaleWallet, WhaleTransaction, PatternInsight, TradingPair, ShadowTrade
from ..services import SolanaWhaleTracker, PatternEngine
from dashboard.services import get_top_scored_whales
from dashboard.whale_scoring import WhaleScoringEngine
from dashboard.whale_analysis import WhaleAnalysisEngine
from .utils import ajax_rate_limit

@login_required
def whale_insights(request):
    """Vista para seguimiento de ballenas y análisis de patrones."""
    try:
        # BYPASS TEMPORAL: No calcular el top global en vivo porque colapsa la RAM si hay muchas ballenas
        top_whales = []
        
        # BYPASS TEMPORAL: Mostrar solo las 10 billeteras más recientes para no saturar memoria en el For Loop
        wallets = WhaleWallet.objects.annotate(
            tx_count=Count('transactions', distinct=True),
            trade_count=Count('shadow_trades', distinct=True)
        ).order_by('-created_at')[:10]
        
        # Sincronizar billeteras si se solicita (Envío a Celery Background Task)
        if request.GET.get('sync') == '1':
            from dashboard.tasks import sync_all_whales_task
            try:
                # Encolar la tarea
                sync_all_whales_task.delay()
                messages.success(request, "Sincronización masiva iniciada en segundo plano. Los datos se actualizarán pronto sin colgar la web.")
            except Exception as e:
                messages.error(request, f"Error al encolar tarea de sincronización: {e}. ¿Está corriendo Redis/Celery?")
            
            return redirect('whale_insights')

        insights = PatternInsight.objects.all().order_by('-detected_at')[:20]
        
        # Calcular P&L para cada billetera 
        for wallet in wallets:
            cache_key = f"wallet_score_{wallet.id}"
            cached_data = cache.get(cache_key)
            if cached_data:
                wallet.pnl_stats = cached_data.get('pnl')
                wallet.score_data = cached_data.get('score')
            else:
                wallet.pnl_stats = {'total_pnl': 0, 'win_rate': 0, 'status': 'Cargando...'}
                wallet.score_data = {'score': 0, 'tier': 'Calculando...', 'category': {'name': 'Pendiente', 'color': 'gray'}}
            
        shadow_trades = ShadowTrade.objects.filter(status='OPEN').order_by('-created_at')
        
        for trade in shadow_trades:
            trade.current_price = None
            trade.live_pnl = None
        
        hot_tokens = []
            
        context = {
            'wallets': wallets,
            'insights': insights,
            'shadow_trades': shadow_trades,
            'hot_tokens': hot_tokens,
            'page_title': 'Whale Insights & Alpha',
            'top_scored_whales': top_whales,
            'pairs': TradingPair.objects.all(),
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
