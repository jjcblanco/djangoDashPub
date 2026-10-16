"""
trading_safety.py
=================
Utilidades centrales de seguridad para el trading (Fase 2).

Concentra:
- kill_switch_active(): lectura fail-closed del Kill-Switch global.
- new_client_order_id(): clientOrderId idempotente para órdenes de Binance.
- force_close_scalping_trade(): cierre seguro de un ScalpingTrade live
  con estado CLOSE_FAILED si la venta real falla.
"""
import logging
import uuid

from django.utils import timezone
from django.db import transaction

from .utils.notifications import send_telegram_message

logger = logging.getLogger(__name__)


def kill_switch_active() -> bool:
    """
    Lee el Kill-Switch global. FAIL-CLOSED: ante cualquier error de lectura,
    se trata como ACTIVO (no operar).
    """
    try:
        from .models import GlobalSettings
        settings, _ = GlobalSettings.objects.get_or_create(id=1)
        return bool(settings.kill_switch_active)
    except Exception as e:
        logger.error(f"[Safety] No se pudo leer el kill_switch; asumiendo ACTIVO: {e}")
        return True


def new_client_order_id(prefix: str, bot_id: int) -> str:
    """
    Genera un clientOrderId válido para Binance (máx 36 chars,
    solo letras/dígitos/underscore).
    Prefijos: cdash_lb (entrada LiveBot), cdash_lbx (salida LiveBot),
              cdash_sb (entrada Scalping),  cdash_sbx (salida Scalping).
    """
    return f"{prefix}{bot_id}_{uuid.uuid4().hex[:16]}"


def force_close_scalping_trade(trade, reason: str = 'CLOSED_EMERGENCY'):
    """
    Cierra un ScalpingTrade live a mercado con clientOrderId idempotente.
    Si la venta real falla → status='CLOSE_FAILED' y NO se toca PnL ni stats.
    Retorna True si cerró, False si quedó CLOSE_FAILED.
    """
    from .models import ScalpingTrade
    from .pair_scanner import _get_exchange

    bot = trade.bot

    with transaction.atomic():
        trade = ScalpingTrade.objects.select_for_update().get(id=trade.id)
        if trade.status not in ('OPEN', 'CLOSE_FAILED'):
            return False

        if not bot.is_live:
            # SIM: cerrar localmente con precio del ticker
            exit_price = None
            try:
                exchange = _get_exchange()
                if exchange:
                    ticker = exchange.fetch_ticker(bot.pair.symbol)
                    exit_price = float(ticker.get('last', 0) or 0)
            except Exception:
                exit_price = None
            if not exit_price:
                exit_price = float(trade.entry_price)
            trade.exit_price = exit_price
            trade.exit_time = timezone.now()
            trade.status = reason
            trade.close_reason = reason
            trade.save(update_fields=['exit_price', 'exit_time', 'status', 'close_reason'])
            return True

        # LIVE: vender a mercado con clientOrderId persistido
        cid = trade.exit_client_order_id or new_client_order_id('cdash_sbx', bot.id)
        try:
            exchange = _get_exchange()
            if not exchange:
                raise Exception("No se pudo conectar a Binance.")

            side_close = 'sell' if trade.side == 'BUY' else 'buy'
            order = exchange.create_market_order(
                bot.pair.symbol, side_close, float(trade.quantity),
                params={'newClientOrderId': cid},
            )
            exit_price = float(order.get('price') or order.get('average') or 0)
            if exit_price <= 0:
                ticker = exchange.fetch_ticker(bot.pair.symbol)
                exit_price = float(ticker.get('last', 0))

            trade.exit_price = exit_price
            trade.exit_time = timezone.now()
            trade.exit_order_id = str(order.get('id', ''))
            trade.status = reason
            trade.close_reason = reason
            trade.exit_client_order_id = cid
            trade.save(update_fields=['exit_price', 'exit_time', 'exit_order_id',
                                      'status', 'close_reason', 'exit_client_order_id'])
            return True

        except Exception as e:
            logger.error(f"[Safety] Error cerrando ScalpingTrade {trade.id} ({reason}): {e}")
            trade.exit_client_order_id = cid
            trade.status = 'CLOSE_FAILED'
            trade.close_reason = reason
            trade.save(update_fields=['exit_client_order_id', 'status', 'close_reason'])
            bot.last_error = f"CLOSE_FAILED trade {trade.id}: {e}"[:250]
            bot.save(update_fields=['last_error'])
            try:
                send_telegram_message(
                    f"⚠️ <b>CLOSE_FAILED</b> (scalping)\n"
                    f"Trade {trade.id} ({bot.pair.symbol}) no se pudo cerrar.\n"
                    f"Error: {str(e)[:100]}\n"
                    f"Requiere intervención manual en Binance."
                )
            except Exception:
                pass
            return False
