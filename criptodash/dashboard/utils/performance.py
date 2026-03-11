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
    Esta función calcula el valor real de la cuenta en Binance y lo compara 
    con el capital inyectado para determinar el desempeño histórico.
    """
    try:
        today = timezone.now().date()
        
        # 1. Capital Inyectado Total (Suma de todas las fundings)
        try:
            total_invested = CapitalFunding.objects.aggregate(total=Sum('amount'))['total'] or Decimal("0")
        except Exception as e:
            logger.error(f"Error calculando total_invested: {e}")
            total_invested = Decimal("0")
        
        # 2. Balance Total Real de Binance (USDT)
        # Obtenemos el balance real directamente del exchange
        binance_total = Decimal("0")
        try:
            bal = exchange.fetch_balance()
            binance_total = Decimal(str(bal['total'].get('USDT', 0)))
        except Exception as e:
            logger.error(f"Error fetching binance balance for snapshot: {e}")
            # Si falla el exchange, no podemos registrar una métrica precisa.
            return None

        # 3. PnL Real Acumulado (Saldo Actual - Capital Inyectado)
        # Este valor representa el crecimiento (o decrecimiento) neto de la cuenta.
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
        
        if created:
            logger.info(f"Snapshot diario creado: Date={today}, Balance={binance_total}, PnL={total_pnl}")
        else:
            logger.info(f"Snapshot diario actualizado: Date={today}, Balance={binance_total}, PnL={total_pnl}")
            
        return metric
        
    except Exception as e:
        logger.error(f"Error crítico en snapshot_daily_metrics: {e}")
        return None
