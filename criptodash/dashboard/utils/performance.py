import logging
from decimal import Decimal
from django.utils import timezone
from django.db.models import Sum
from ..models import LiveBot, CapitalFunding, DailyMetric
from ..ccxttest1 import binance as exchange
from django.conf import settings

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
        api_key = None
        try:
            import ccxt
            # --- BLINDAJE DE AUTENTICACIÓN ---
            api_key = getattr(settings, 'BINANCE_APIKEY', None)
            api_secret = getattr(settings, 'BINANCE_SECRET', None)
            
            if not api_key:
                err_msg = "API Key no encontrada en settings. Revisa el archivo .env en el VPS."
                logger.error(err_msg)
                return None, err_msg
            
            # Instancia local para evitar problemas con el objeto global
            local_exchange = ccxt.binance({
                'apiKey': api_key,
                'secret': api_secret,
                'enableRateLimit': True,
                'options': {
                    'recvWindow': 60000,
                    'adjustForTimeDifference': True,
                }
            })
            
            bal = local_exchange.fetch_balance()
            binance_total = Decimal(str(bal['total'].get('USDT', 0)))
        except Exception as e:
            # Reportar el tipo de error y fragmentos de las llaves para diagnóstico
            key_hint = f"key:...{api_key[-4:] if api_key else 'None'}"
            secret_hint = f"secret:...{api_secret[-4:] if api_secret else 'None'}"
            err_msg = f"{type(e).__name__}: {str(e)} ({key_hint}, {secret_hint})"
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
