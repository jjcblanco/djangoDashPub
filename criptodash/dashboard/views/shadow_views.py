from decimal import Decimal
from django.shortcuts import redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.core.cache import cache

from ..models import ShadowTrade, WhaleWallet
from dashboard.services import fetch_current_price
from .utils import ajax_rate_limit

@login_required
@require_POST
def simulate_whale_trade(request):
    """Simula una copia de trade de ballena (Shadow Trading)."""
    try:
        wallet_id = request.POST.get('wallet_id')
        symbol = request.POST.get('symbol', 'SOL')
        mint = request.POST.get('mint', '')
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
        trade = get_object_or_404(ShadowTrade, id=trade_id)
        
        exit_val = request.POST.get('exit_price')
        if exit_val:
            exit_price = Decimal(exit_val)
        else:
            real_price = fetch_current_price(trade.token_symbol)
            if real_price:
                exit_price = Decimal(str(real_price))
            else:
                exit_price = trade.entry_price
        
        trade.exit_price = exit_price
        trade.status = 'CLOSED'
        trade.closed_at = timezone.now()
        
        trade.pnl_percent = float((trade.exit_price - trade.entry_price) / trade.entry_price * 100)
        trade.save()
        
        messages.success(request, f"Simulación de {trade.token_symbol} cerrada con {trade.pnl_percent:.2f}% de P&L.")
    except Exception as e:
        messages.error(request, f"Error al cerrar simulación: {e}")
        
    return redirect('whale_insights')

@login_required
@ajax_rate_limit(max_calls=50, period_seconds=60)
def whale_live_prices(request):
    """Retorna precios en vivo de los Shadow Trades abiertos. Llamado vía AJAX post-pageload."""
    shadow_trades = ShadowTrade.objects.filter(status='OPEN').values('id', 'token_symbol', 'entry_price')
    result = []
    
    for trade in shadow_trades:
        symbol = trade['token_symbol']
        cache_key = f"live_price_{symbol}"
        current_price = cache.get(cache_key)
        
        if not current_price:
            try:
                current_price = fetch_current_price(symbol)
                if current_price:
                    cache.set(cache_key, current_price, 60 * 5)
            except Exception:
                current_price = None
        
        entry = float(trade['entry_price']) if trade['entry_price'] else 0
        live_pnl = None
        if current_price and entry > 0:
            live_pnl = round(((current_price - entry) / entry) * 100, 2)
        
        result.append({
            'trade_id': trade['id'],
            'symbol': symbol,
            'current_price': current_price,
            'live_pnl': live_pnl,
        })
    
    return JsonResponse({'status': 'ok', 'trades': result})
