import pandas as pd
import logging
from datetime import datetime
from decimal import Decimal
from django.utils import timezone
from .models import LiveBot, LiveTrade, TradingPair
from .backtester import GridStrategy, DayTradingStrategy
from .ccxttest1 import historical_fetch_ohlcv, binance as exchange

logger = logging.getLogger(__name__)

class BotManager:
    """
    Gestiona la ejecución 'en vivo' de múltiples bots de trading.
    """

    @staticmethod
    def update_all_active_bots():
        """Ciclo principal de actualización para todos los bots activos."""
        active_bots = LiveBot.objects.filter(status__in=['RUNNING', 'CLOSE_ONLY'])
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
                import traceback
                error_trace = traceback.format_exc()
                logger.error(f"Error actualizando bot {bot.id}: {e}\n{error_trace}")
                bot.status = 'ERROR'
                # Guardamos el error y una pista del traceback para depuración
                bot.last_error = f"{str(e)} | Trace: {error_trace.splitlines()[-2] if len(error_trace.splitlines()) > 1 else 'no-trace'}"
                bot.save()
        return results

    @staticmethod
    def update_bot(bot):
        """Ejecuta un ciclo de decisión para un bot específico."""
        # 1. Obtener datos recientes
        timeframe = bot.parameters.get('timeframe', '1h')
        df = BotManager._get_live_df(bot.pair.symbol, timeframe=timeframe)
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
        
        # 0. Verificar Inicialización (Bootstrap)
        # Solo inicializamos si no hay operaciones ACTIVAS (OPEN o WAITING)
        active_trades_exist = LiveTrade.objects.filter(bot=bot, status__in=['OPEN', 'WAITING']).exists()
        
        if not active_trades_exist and bot.status == 'RUNNING':
            logger.info(f"Bot {bot.id} ({bot.name}) no tiene operaciones activas. Iniciando Bootstrap...")
            return BotManager._grid_bootstrap(bot, current_price, grid_levels)

        # Obtener posiciones abiertas del bot
        open_trades = LiveTrade.objects.filter(bot=bot).exclude(status__in=['CLOSED', 'CANCELED'])
        
        # 1. Sincronizar estados con el Exchange
        for trade in open_trades:
            if bot.is_live and trade.order_id:
                try:
                    # Verificar estado de la orden en Binance
                    order = exchange.fetch_order(trade.order_id, bot.pair.symbol)
                    status = order.get('status') # 'open', 'closed', 'canceled'
                    
                    if status == 'closed':
                        if trade.status == 'WAITING':
                            # ¡Compra ejecutada! Pasamos a OPEN y colocamos TP
                            trade.status = 'OPEN'
                            tp_price = float(trade.entry_price) + grid_step
                            
                            exit_order_id = None
                            try:
                                tp_order = exchange.create_order(
                                    symbol=bot.pair.symbol,
                                    type='limit',
                                    side='sell',
                                    amount=float(trade.amount),
                                    price=tp_price
                                )
                                exit_order_id = tp_order.get('id')
                            except Exception as e:
                                logger.error(f"Error colocando TP para bot {bot.id}: {e}")
                                # Si falla el TP, el trade queda OPEN pero sin exit_order_id (requiere intervención o reintento)
                            
                            trade.exit_order_id = exit_order_id
                            trade.save()
                            logger.info(f"Trade {trade.id} llenado (BUY). Colocado TP LIMIT en {tp_price}")

                        elif trade.status == 'OPEN' and trade.exit_order_id:
                            # ¡Venta (TP) ejecutada! Cerramos trade y reponemos nivel
                            BotManager._close_trade(trade, order.get('price', current_price), "GRID_LIMIT_TP")
                            
                            # Reponer la orden de compra en este nivel (si el bot sigue RUNNING)
                            if bot.status == 'RUNNING':
                                BotManager._repose_limit_buy(bot, trade.entry_price)

                    elif status == 'canceled':
                        trade.status = 'CANCELED'
                        trade.save()
                except Exception as e:
                    logger.error(f"Error sincronizando orden {trade.order_id}: {e}")

            else:
                # LÓGICA DE SIMULACIÓN (Papertrading local sin órdenes reales)
                if trade.status == 'WAITING' and current_price <= float(trade.entry_price):
                    trade.status = 'OPEN'
                    trade.save()
                    logger.info(f"[PAPER] Trade {trade.id} comprado en {trade.entry_price}")
                elif trade.status == 'OPEN':
                    target_tp = float(trade.entry_price) + grid_step
                    if current_price >= target_tp:
                        BotManager._close_trade(trade, current_price, "GRID_PAPER_TP")
                        if bot.status == 'RUNNING':
                            BotManager._repose_limit_buy(bot, trade.entry_price)

        # 2. Verificar Stop Loss Global (Si el precio cae por debajo del SL, cancelar todo)
        if stop_loss_price and current_price <= stop_loss_price:
            BotManager._handle_global_stop(bot, open_trades, current_price)
            return {'bot_id': bot.id, 'action': 'STOPPED_BY_SL'}

        # 3. Verificar Grid Trailing (Si el precio supera el rango superior y está activo)
        if bot.parameters.get('trailing_enabled') and current_price > float(upper):
            BotManager._handle_grid_trailing(bot, current_price, grid_step, upper)
        
        # 4. Verificar Grid Trailing DOWN (NUEVO)
        if bot.parameters.get('trailing_down') and current_price < float(lower):
            BotManager._handle_grid_trailing_down(bot, current_price, grid_step, lower)

        return {'bot_id': bot.id, 'status': 'synced'}

    @staticmethod
    def _repose_limit_buy(bot, price):
        """Vuelve a colocar una orden de compra en un nivel que acaba de venderse."""
        amount_per_level = float(bot.parameters.get('amount_per_level'))
        # 1% de margen para comisiones
        safe_amount = amount_per_level * 0.99
        qty = safe_amount / float(price)
        order_id = None
        
        if bot.is_live:
            try:
                # Ajustar a precisión de Binance
                qty = float(exchange.amount_to_precision(bot.pair.symbol, qty))
                price_adj = float(exchange.price_to_precision(bot.pair.symbol, float(price)))
                
                api_order = exchange.create_order(bot.pair.symbol, 'limit', 'buy', qty, price_adj)
                order_id = api_order.get('id')
            except Exception as e:
                logger.error(f"Error reponiendo nivel {price} para bot {bot.id}: {e}")
        
        LiveTrade.objects.create(
            bot=bot, side='BUY', entry_price=price, amount=Decimal(str(qty)),
            status='WAITING', order_id=order_id
        )
        # Descontar del balance
        cost = Decimal(str(amount_per_level))
        fee = cost * Decimal("0.001")
        bot.current_balance -= (cost + fee)
        bot.save()

    @staticmethod
    def _handle_global_stop(bot, open_trades, current_price):
        """Cancela órdenes y vende todo en caso de Stop Loss."""
        logger.warning(f"STOP LOSS GLOBAL activado para bot {bot.id}")
        for trade in open_trades:
            if bot.is_live and trade.order_id:
                try:
                    exchange.cancel_order(trade.order_id, bot.pair.symbol)
                    if trade.exit_order_id: exchange.cancel_order(trade.exit_order_id, bot.pair.symbol)
                except: pass
            
            if trade.status == 'OPEN':
                BotManager._close_trade(trade, current_price, "GLOBAL_STOP_LOSS")
            else:
                trade.status = 'CANCELED'
                trade.save()
        
        bot.status = 'STOPPED'
        bot.last_error = f"STOP LOSS GLOBAL ACTIVADO en {current_price}"
        bot.save()

    @staticmethod
    def _handle_grid_trailing(bot, current_price, grid_step, old_upper):
        """Desplaza el rango de la malla hacia arriba siguiendo el precio."""
        logger.info(f"GRID TRAILING UP: El precio {current_price} superó el límite {old_upper}. Desplazando malla hacia arriba.")
        
        # Desplazar parámetros
        bot.parameters['upper_price'] = str(float(bot.parameters['upper_price']) + grid_step)
        bot.parameters['lower_price'] = str(float(bot.parameters['lower_price']) + grid_step)
        
        # 1. Localizar el trade con el precio de entrada más bajo que esté WAITING
        bottom_trade = LiveTrade.objects.filter(bot=bot, status='WAITING').order_by('entry_price').first()
        
        if bottom_trade:
            logger.info(f"GRID TRAILING UP: Cancelando orden inferior {bottom_trade.entry_price}")
            if bot.is_live and bottom_trade.order_id:
                try: exchange.cancel_order(bottom_trade.order_id, bot.pair.symbol)
                except Exception as e: logger.error(f"Error cancelando orden inferior en Trailing: {e}")
            
            bottom_trade.status = 'CANCELED'
            bottom_trade.save()
            # 2. Añadir nueva orden de compra en el nivel superior (el que era old_upper)
            BotManager._repose_limit_buy(bot, old_upper)
        
        bot.save()

    @staticmethod
    def _handle_grid_trailing_down(bot, current_price, grid_step, old_lower):
        """Desplaza el rango de la malla hacia abajo siguiendo el precio."""
        logger.info(f"GRID TRAILING DOWN: El precio {current_price} cayó bajo el límite {old_lower}. Desplazando malla hacia abajo.")
        
        # Desplazar parámetros
        bot.parameters['upper_price'] = str(float(bot.parameters['upper_price']) - grid_step)
        bot.parameters['lower_price'] = str(float(bot.parameters['lower_price']) - grid_step)
        
        # 1. Localizar el trade con el precio de entrada más ALTO (el nivel superior)
        top_trade = LiveTrade.objects.filter(bot=bot).exclude(status__in=['CLOSED', 'CANCELED']).order_by('-entry_price').first()
        
        if top_trade:
            if top_trade.status == 'WAITING':
                logger.info(f"GRID TRAILING DOWN: Cancelando nivel superior WAITING en {top_trade.entry_price}")
                if bot.is_live and top_trade.order_id:
                    try: exchange.cancel_order(top_trade.order_id, bot.pair.symbol)
                    except Exception as e: logger.error(f"Error cancelando orden superior: {e}")
                top_trade.status = 'CANCELED'
                top_trade.save()
            elif top_trade.status == 'OPEN':
                logger.info(f"GRID TRAILING DOWN: Vendiendo nivel superior OPEN en {top_trade.entry_price} (STOP LOSS INDIVIDUAL)")
                # Cerramos la operación (vender a precio actual para recuperar capital)
                BotManager._close_trade(top_trade, current_price, "GRID_TRAILING_DOWN_LOSS")
            
            # 2. Añadir nueva orden de compra en el fondo (el nuevo lower_price)
            new_lower = float(bot.parameters['lower_price'])
            logger.info(f"GRID TRAILING DOWN: Añadiendo nueva orden de compra en el fondo {new_lower}")
            BotManager._repose_limit_buy(bot, new_lower)
            
        bot.save()

    @staticmethod
    def _grid_bootstrap(bot, current_price, grid_levels):
        """
        Inicialización completa de la malla:
        1. Para niveles < precio_actual: Coloca LIMIT BUY (Esperando caída).
        2. Para niveles > precio_actual: Compra a MERCADO y coloca LIMIT SELL (TP) inmediatamente.
        """
        logger.info(f"Iniciando Bootstrap COMPLETO para bot {bot.id} ({bot.name})")
        params = bot.parameters
        amount_per_level = float(params.get('amount_per_level', 0))
        grid_step = (float(params.get('upper_price')) - float(params.get('lower_price'))) / (int(params.get('grid_levels')) - 1)
        
        buy_orders = 0
        market_buys = 0
        
        # --- NUEVO: Verificación Proactiva de Saldo y Filtros ---
        if bot.is_live:
            try:
                # 1. Verificar Balance Libre
                balance = exchange.fetch_balance()
                free_usdt = float(balance['free'].get('USDT', 0))
                total_required = amount_per_level * len(grid_levels)
                
                if free_usdt < total_required:
                    error_msg = f"Saldo LIBRE insuficiente: Tienes {free_usdt:.2f} USDT libres, pero el bot requiere {total_required:.2f} USDT para todos los niveles. (Tienes otros {float(balance['total'].get('USDT', 0)) - free_usdt:.2f} USDT bloqueados en otras órdenes)."
                    bot.last_error = error_msg
                    bot.status = 'STOPPED'
                    bot.save()
                    return {'bot_id': bot.id, 'error': 'insufficient_funds'}

                # 2. Verificar Min Notional (Monto mínimo por nivel)
                market = exchange.market(bot.pair.symbol)
                min_cost = market['limits']['cost']['min']
                if amount_per_level < min_cost:
                    error_msg = f"Monto insuficiente por nivel: {amount_per_level} USDT es inferior al mínimo de Binance ({min_cost} USDT)."
                    bot.last_error = error_msg
                    bot.status = 'STOPPED'
                    bot.save()
                    return {'bot_id': bot.id, 'error': 'min_notional_fail'}

            except Exception as e:
                logger.warning(f"No se pudo verificar balance/filtros proactivamente: {e}")
                # Continuamos, pero es probable que falle luego si hay problemas reales
        
        for level in grid_levels:
            # 1% de margen para comisiones
            safe_amount = amount_per_level * 0.99
            qty = safe_amount / level
            order_id = None
            exit_order_id = None
            status = 'WAITING'
            
            if bot.is_live:
                try:
                    qty = float(exchange.amount_to_precision(bot.pair.symbol, qty))
                except: pass

            # --- NIVEL INFERIOR: LIMIT BUY ---
            if level < current_price:
                if bot.is_live:
                    try:
                        price_adj = float(exchange.price_to_precision(bot.pair.symbol, level))
                        api_order = exchange.create_order(bot.pair.symbol, 'limit', 'buy', qty, price_adj)
                        order_id = api_order.get('id')
                    except Exception as e:
                        logger.error(f"Error Bootstrap (Limit Buy) bot {bot.id} en {level}: {e}")
                        continue
                
                LiveTrade.objects.create(
                    bot=bot, side='BUY', entry_price=Decimal(str(level)),
                    amount=Decimal(str(qty)), status='WAITING', order_id=order_id
                )
                buy_orders += 1

            # --- NIVEL SUPERIOR: MARKET BUY + LIMIT SELL (TP) ---
            else:
                entry_price = current_price
                if bot.is_live:
                    try:
                        # Comprar a mercado
                        market_order = exchange.create_order(bot.pair.symbol, 'market', 'buy', qty)
                        entry_price = float(market_order.get('price', current_price))
                        order_id = market_order.get('id')
                        
                        # Colocar TP inmediatamente (LIMIT SELL)
                        tp_price = level + grid_step # El TP es el siguiente nivel
                        tp_price_adj = float(exchange.price_to_precision(bot.pair.symbol, tp_price))
                        
                        tp_order = exchange.create_order(bot.pair.symbol, 'limit', 'sell', qty, tp_price_adj)
                        exit_order_id = tp_order.get('id')
                    except Exception as e:
                        logger.error(f"Error Bootstrap (Market/TP) bot {bot.id} en {level}: {e}")
                        continue
                
                LiveTrade.objects.create(
                    bot=bot, side='BUY', entry_price=Decimal(str(entry_price)),
                    amount=Decimal(str(qty)), status='OPEN', order_id=order_id,
                    exit_order_id=exit_order_id
                )
                market_buys += 1

            # Descontar del balance (monto + comisión 0.1%)
            cost = Decimal(str(amount_per_level))
            fee = cost * Decimal("0.001")
            bot.current_balance -= (cost + fee)

        bot.save()
        logger.info(f"Bootstrap fin: {buy_orders} LIMIT BUY, {market_buys} MARKET BUY + TP.")
        return {'bot_id': bot.id, 'status': 'bootstrapped', 'limit_buys': buy_orders, 'market_buys': market_buys}

    @staticmethod
    def _manage_daytrading_bot(bot, df):
        """Lógica para bots de Day Trading en tiempo real."""
        # Casting preventivo de parámetros para evitar TypeError
        clean_params = {}
        for k, v in bot.parameters.items():
            try:
                if isinstance(v, str):
                    if '.' in v: clean_params[k] = float(v)
                    else: clean_params[k] = int(v)
                else:
                    clean_params[k] = v
            except:
                clean_params[k] = v
        
        strategy = DayTradingStrategy(parameters=clean_params)
        df_with_signals = strategy.generate_signals(df)
        last_row = df_with_signals.iloc[-1]
        signal = last_row.get('signal')
        current_price = float(last_row['close'])
        
        open_trade = LiveTrade.objects.filter(bot=bot, status='OPEN').first()
        
        # 1. Monitoreo Activo de SL/TP (Gestión de Riesgo)
        if open_trade:
            sl = float(open_trade.stop_loss) if open_trade.stop_loss else None
            tp = float(open_trade.take_profit) if open_trade.take_profit else None
            
            # Trailing Stop Loss (Opcional - se puede parametrizar)
            # Si el precio sube un 1% por encima del precio de entrada, movemos el SL al precio de entrada (Break-even)
            if sl and current_price > float(open_trade.entry_price) * 1.01:
                new_sl = float(open_trade.entry_price)
                if new_sl > sl:
                    open_trade.stop_loss = Decimal(str(new_sl))
                    open_trade.save()
                    logger.info(f"Bot {bot.id}: Trailing SL movido a break-even ({new_sl})")
            
            # Ejecución de SL
            if sl and current_price <= sl:
                logger.info(f"Bot {bot.id}: Cerrando por STOP LOSS en {current_price}")
                BotManager._close_trade(open_trade, current_price, "STOP_LOSS")
                return {'bot_id': bot.id, 'status': 'sl_hit'}
                
            # Ejecución de TP
            if tp and current_price >= tp:
                logger.info(f"Bot {bot.id}: Cerrando por TAKE PROFIT en {current_price}")
                BotManager._close_trade(open_trade, current_price, "TAKE_PROFIT")
                return {'bot_id': bot.id, 'status': 'tp_hit'}

        # 2. Lógica de Señales
        if signal == 'BUY' and not open_trade:
            # --- NUEVO: Verificación de Saldo Real ---
            if bot.is_live:
                try:
                    balance = exchange.fetch_balance()
                    free_usdt = float(balance['free'].get('USDT', 0))
                    if free_usdt < float(bot.current_balance):
                        msg = f"Saldo insuficiente en Exchange: Necesitas {bot.current_balance:.2f} USDT, tienes {free_usdt:.2f} USDT libres."
                        bot.last_error = msg
                        bot.status = 'ERROR'
                        bot.save()
                        logger.warning(f"Bot {bot.id}: {msg}")
                        return {'bot_id': bot.id, 'error': 'insufficient_funds'}
                except Exception as e:
                    logger.error(f"Error verificando balance para bot {bot.id}: {e}")
                    # Si falla la API, mejor no intentar la compra
                    return {'bot_id': bot.id, 'error': 'api_error'}

            # Abrir posición con todo el balance del bot
            balance = float(bot.current_balance)
            amount = balance / current_price
            
            sl = last_row.get('stop_loss')
            tp = last_row.get('take_profit')
            
            LiveTrade.objects.create(
                bot=bot,
                side='BUY',
                entry_price=Decimal(str(current_price)),
                amount=Decimal(str(amount)),
                status='OPEN',
                stop_loss=Decimal(str(sl)) if pd.notnull(sl) else None,
                take_profit=Decimal(str(tp)) if pd.notnull(tp) else None
            )
            bot.current_balance = 0
            bot.save()
            logger.info(f"Bot {bot.id}: BUY ejecutado en {current_price}. SL: {sl}, TP: {tp}")
            
        elif signal == 'SELL' and open_trade:
            # Cerrar posición actual por señal de estrategia
            BotManager._close_trade(open_trade, current_price, "STRATEGY_SIGNAL")

        return {'bot_id': bot.id, 'status': 'updated'}

    @staticmethod
    def _close_trade(trade, exit_price, reason):
        """Cierra una operación y actualiza el balance del bot."""
        bot = trade.bot
        
        # 1. Si el bot es live, cerrar en el exchange
        if bot.is_live:
            try:
                # En GRID vendemos a mercado o limit segun el trigger
                exchange.create_order(
                    symbol=bot.pair.symbol,
                    type='market', # Venta rápida al detectar el TP del grid
                    side='sell',
                    amount=float(trade.amount)
                )
                logger.info(f"Cierre REAL (Venta) para trade {trade.id} ({reason})")
            except Exception as e:
                logger.error(f"Error cerrando orden REAL para bot {bot.id}: {e}")
                # Podríamos querer abortar el cierre local, pero por ahora lo marcamos
                # como error para que el usuario intervenga.

        # 2. Actualizar registro local
        # Configuración de comisión (0.1% por operación)
        commission_rate = Decimal("0.001")
        
        # Calcular comisiones (entrada + salida)
        cost_entry = trade.entry_price * trade.amount * commission_rate
        cost_exit = Decimal(str(exit_price)) * trade.amount * commission_rate
        total_commission = cost_entry + cost_exit
        
        # Calcular PnL Neto (Ganancia bruta - Comisiones totales)
        gross_pnl = (Decimal(str(exit_price)) - trade.entry_price) * trade.amount
        net_pnl = gross_pnl - total_commission
        
        trade.exit_price = Decimal(str(exit_price))
        trade.exit_time = timezone.now()
        trade.status = 'CLOSED'
        trade.commission = total_commission
        trade.pnl = net_pnl
        trade.save()
        
        # El balance se actualiza con el revenue neto (Venta - Comisión de salida)
        revenue = (trade.amount * Decimal(str(exit_price))) - cost_exit
        bot.current_balance = Decimal(str(float(bot.current_balance) + float(revenue)))
        bot.save()

    @staticmethod
    def _get_live_df(symbol, timeframe='1h'):
        """Obtiene las últimas velas para análisis en vivo."""
        try:
            bars = historical_fetch_ohlcv(symbol, timeframe=timeframe, limit=100)
            if not bars: return None
            df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            return df
        except Exception as e:
            print(f"Error _get_live_df for {symbol} ({timeframe}): {e}")
            return None
