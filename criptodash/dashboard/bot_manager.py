import pandas as pd
import logging
from datetime import datetime
from decimal import Decimal
from django.utils import timezone
from .models import LiveBot, LiveTrade, TradingPair
from .backtester import GridStrategy, DayTradingStrategy
from .ccxttest1 import historical_fetch_ohlcv

logger = logging.getLogger(__name__)

class BotManager:
    """
    Gestiona la ejecución 'en vivo' de múltiples bots de trading.
    """

    @staticmethod
    def update_all_active_bots():
        """Ciclo principal de actualización para todos los bots activos."""
        active_bots = LiveBot.objects.filter(status='RUNNING')
        results = []
        for bot in active_bots:
            try:
                # Limpiar error previo al intentar actualizar
                if bot.last_error:
                    bot.last_error = None
                    bot.save()
                
                result = BotManager.update_bot(bot)
                results.append(result)
            except Exception as e:
                logger.error(f"Error actualizando bot {bot.id}: {e}")
                bot.status = 'ERROR'
                bot.last_error = str(e)
                bot.save()
        return results

    @staticmethod
    def update_bot(bot):
        """Ejecuta un ciclo de decisión para un bot específico."""
        # 1. Obtener datos recientes
        df = BotManager._get_live_df(bot.pair.symbol)
        if df is None or df.empty:
            return {'bot_id': bot.id, 'status': 'no_data'}

        # 2. Ejecutar según estrategia
        if bot.strategy_type == 'GRID':
            return BotManager._manage_grid_bot(bot, df)
        elif bot.strategy_type == 'DAYTRADING':
            return BotManager._manage_daytrading_bot(bot, df)
        
        return {'bot_id': bot.id, 'status': 'unknown_strategy'}

    @staticmethod
    def _manage_grid_bot(bot, df):
        """Lógica para bots de malla en tiempo real."""
        params = bot.parameters
        current_price = float(df['close'].iloc[-1])
        upper = float(params.get('upper_price'))
        lower = float(params.get('lower_price'))
        levels_count = int(params.get('grid_levels'))
        amount_per_level = float(params.get('amount_per_level'))
        stop_loss_price = params.get('global_stop_loss')
        if stop_loss_price: stop_loss_price = float(stop_loss_price)

        grid_step = (upper - lower) / (levels_count - 1)
        grid_levels = [lower + i * grid_step for i in range(levels_count)]
        
        # Obtener posiciones abiertas del bot
        open_trades = LiveTrade.objects.filter(bot=bot, status='OPEN')
        
        # 1. Verificar Stop Loss Global
        if stop_loss_price and current_price <= stop_loss_price and open_trades.exists():
            for trade in open_trades:
                BotManager._close_trade(trade, current_price, "GLOBAL_STOP_LOSS")
            bot.status = 'STOPPED'
            bot.save()
            return {'bot_id': bot.id, 'action': 'STOPPED_BY_SL'}

        # 2. Verificar Cierres (Take Profit)
        for trade in open_trades:
            # En Grid, el target TP es el siguiente nivel por encima del de entrada
            target_tp = float(trade.entry_price) + grid_step
            if current_price >= target_tp:
                BotManager._close_trade(trade, current_price, "GRID_TP")

        # 3. Verificar Entradas (Nuevas compras)
        if current_price >= (lower - grid_step * 0.5) and current_price <= (upper + grid_step * 0.5):
            for level in grid_levels:
                if current_price <= level:
                    # No comprar si ya hay una posición abierta cerca de este nivel
                    already_bought = any(abs(float(t.entry_price) - level) < (grid_step * 0.1) for t in open_trades)
                    
                    if not already_bought and float(bot.current_balance) >= amount_per_level:
                        # Crear nueva operación 'OPEN'
                        LiveTrade.objects.create(
                            bot=bot,
                            side='BUY',
                            entry_price=Decimal(str(level)), # Usamos el nivel nominal
                            amount=Decimal(str(amount_per_level / current_price)),
                            status='OPEN'
                        )
                        # Actualizar balance del bot
                        bot.current_balance = Decimal(str(float(bot.current_balance) - amount_per_level))
                        bot.save()

        return {'bot_id': bot.id, 'status': 'updated'}

    @staticmethod
    def _manage_daytrading_bot(bot, df):
        """Lógica para bots de Day Trading en tiempo real."""
        strategy = DayTradingStrategy(parameters=bot.parameters)
        df_with_signals = strategy.generate_signals(df)
        last_row = df_with_signals.iloc[-1]
        signal = last_row.get('signal')
        current_price = float(last_row['close'])
        
        open_trade = LiveTrade.objects.filter(bot=bot, status='OPEN').first()
        
        if signal == 'BUY' and not open_trade:
            # Abrir posición con todo el balance del bot
            balance = float(bot.current_balance)
            amount = balance / current_price
            LiveTrade.objects.create(
                bot=bot,
                side='BUY',
                entry_price=Decimal(str(current_price)),
                amount=Decimal(str(amount)),
                status='OPEN'
            )
            bot.current_balance = 0
            bot.save()
        elif signal == 'SELL' and open_trade:
            # Cerrar posición actual
            BotManager._close_trade(open_trade, current_price, "STRATEGY_SIGNAL")

        return {'bot_id': bot.id, 'status': 'updated'}

    @staticmethod
    def _close_trade(trade, exit_price, reason):
        """Cierra una operación y actualiza el balance del bot."""
        trade.exit_price = Decimal(str(exit_price))
        trade.exit_time = timezone.now()
        trade.status = 'CLOSED'
        
        # Simplificamos comisión al 0.1%
        pnl = (Decimal(str(exit_price)) - trade.entry_price) * trade.amount
        trade.pnl = pnl
        trade.save()
        
        bot = trade.bot
        revenue = trade.amount * Decimal(str(exit_price)) * Decimal("0.999")
        bot.current_balance = Decimal(str(float(bot.current_balance) + float(revenue)))
        bot.save()

    @staticmethod
    def _get_live_df(symbol):
        """Obtiene las últimas velas para análisis en vivo."""
        try:
            bars = historical_fetch_ohlcv(symbol, timeframe='1h', limit=100)
            if not bars: return None
            df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            return df
        except Exception:
            return None
