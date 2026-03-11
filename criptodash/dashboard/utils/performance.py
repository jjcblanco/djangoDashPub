import logging
from decimal import Decimal
from django.utils import timezone
from django.db.models import Sum
from ..models import LiveBot, CapitalFunding, DailyMetric
from ..ccxttest1 import binance as exchange

logger = logging.getLogger(__name__)

def snapshot_daily_metrics():
    """
    Registra una captura de las métricas de capital del día.
    Retorna: (DailyMetric object o None, error_string o None)
    """
    try:
        today = timezone.now().date()
        
        # 1. Capital Inyectado Total
        try:
            total_invested = CapitalFunding.objects.aggregate(total=Sum('amount'))['total'] or Decimal("0")
        except Exception as e:
            logger.error(f"Error calculando total_invested: {e}")
            total_invested = Decimal("0")
        
        # 2. Balance Total Real de Binance (USDT)
        binance_total = Decimal("0")
        try:
            # Asegurarse de que los mercados estén cargados si es necesario
            if hasattr(exchange, 'load_markets'):
                exchange.load_markets()
                
            bal = exchange.fetch_balance()
            binance_total = Decimal(str(bal['total'].get('USDT', 0)))
        except Exception as e:
            err_msg = f"{type(e).__name__}: {str(e)}"
            logger.error(f"Error fetching binance balance for snapshot: {err_msg}")
            return None, err_msg

        # 3. PnL Real Acumulado
        total_pnl = binance_total - total_invested
        
        # 4. Guardar o actualizar la entrada para hoy
        metric, created = DailyMetric.objects.update_or_create(
            date=today,
            defaults={
                'total_balance': binance_total,
                'total_pnl': total_pnl,
                'total_invested': total_invested
            }
        )
        
        return metric, None
        
    except Exception as e:
        err_msg = f"Critical error: {str(e)}"
        logger.error(err_msg)
        return None, err_msg
