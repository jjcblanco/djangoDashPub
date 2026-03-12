import pandas as pd
import numpy as np
from decimal import Decimal
from django.utils import timezone
from datetime import datetime
from .models import BacktestResult, TradingPair, TradeSignal, OHLCVData
from .data_service import DataManager
from .indicadores import *
from .ccxttest1 import signals as generate_signals_from_ccxt
import plotly.graph_objs as go


class TradingStrategy:
    """Clase base para estrategias de trading"""
    def __init__(self, name, parameters=None):
        self.name = name
        self.parameters = parameters or {}

    def generate_signals(self, df):
        """Método a implementar por cada estrategia"""
        raise NotImplementedError("Subclasses must implement generate_signals")


class SignalBasedStrategy(TradingStrategy):
    """Estrategia que usa señales existentes de la base de datos"""
    def __init__(self, parameters=None):
        super().__init__("Signal-Based", parameters)

    def generate_signals(self, df):
        """
        Esta estrategia no genera señales, las toma del DataFrame
        que ya debe contener la columna 'signal' con valores BUY/SELL/HOLD
        """
        if 'signal' not in df.columns:
            df['signal'] = 'HOLD'
        return df


class DayTradingStrategy(TradingStrategy):
    """
    Estrategia de Day Trading / Scalping basada en EMA Ribbon y RSI.
    Diseñada para temporalidades bajas (5m, 15m).
    Lógica:
    - Compra: EMA 9 > EMA 21, y ambas sobre EMA 50 y EMA 200. RSI > 55.
    - Venta: EMA 9 < EMA 21, y ambas bajo EMA 50 y EMA 200. RSI < 45.
    """
    def __init__(self, parameters=None):
        super().__init__("Day Trading (EMA Ribbon Scalper)", parameters)
        # Parámetros por defecto si no vienen especificados
        default_params = {
            'ema_fast': 9,
            'ema_med': 21,
            'ema_slow': 50,
            'ema_trend': 200,
            'rsi_period': 14,
            'rsi_buy': 55,
            'rsi_sell': 45,
            'atr_sl': 1.5,          # Corregido: SL más ajustado para mejor RR
            'atr_tp': 3.0,          # Corregido: TP más amplio -> RR mínimo 1:2
            'use_candles': True,
            'min_strength': 4, # Requerimiento base para modo Balanceado
            'min_adx': 20,     # Mínimo de tendencia para operar
            'strategy_mode': 'balanced', # opciones: conservative, balanced, aggressive
            'use_bollinger_filter': True,
            'cooldown_bars': 3,     # Velas de espera mínima entre trades
            'risk_per_trade_pct': 2.0  # % del balance a arriesgar por trade
        }
        # Mezclar con los pasados y asegurar tipos numéricos
        self.parameters = {**default_params, **(parameters or {})}
        
        # Casting explícito para evitar TypeError (str vs int)
        # Convertimos TODO lo que debería ser numérico
        if self.parameters:
            for key in list(self.parameters.keys()):
                val = self.parameters[key]
                if isinstance(val, str):
                    try:
                        if '.' in val: self.parameters[key] = float(val)
                        else: self.parameters[key] = int(val)
                    except (ValueError, TypeError):
                        pass

    def generate_signals(self, df):
        # 1. Calcular indicadores base
        # Asegurar que los periodos son int
        ema_f = int(self.parameters.get('ema_fast', 9))
        ema_m = int(self.parameters.get('ema_med', 21))
        ema_s = int(self.parameters.get('ema_slow', 50))
        ema_t = int(self.parameters.get('ema_trend', 200))

        df['ema9'] = df['close'].ewm(span=ema_f, adjust=False).mean()
        df['ema21'] = df['close'].ewm(span=ema_m, adjust=False).mean()
        df['ema50'] = df['close'].ewm(span=ema_s, adjust=False).mean()
        df['ema200'] = df['close'].ewm(span=ema_t, adjust=False).mean()
        df = macd(df) # MACD default (12, 26, 9)
        df['rsi'] = calculate_rsi(df, int(self.parameters.get('rsi_period', 14)))
        df['atr'] = atr(df, 14)
        
        if 'adx' not in df.columns:
            df['adx'] = adx(df, 14)
        if 'obv' not in df.columns:
            df['obv'] = obv(df)
        if 'senkou_a' not in df.columns:
            df = ichimoku_cloud(df)
            
        df = detect_candlestick_patterns(df)
        
        # 2. Inicializar columnas de señales
        df['strength'] = 0.0
        df['signal'] = 'HOLD'
        df['stop_loss'] = np.nan
        df['take_profit'] = np.nan
        
        # 3. Calcular Fortaleza (Independiente de la señal de entrada)
        # EMA Alignment (2 pts)
        df.loc[(df['close'] > df['ema50']) & (df['close'] > df['ema200']), 'strength'] += 2
        df.loc[(df['close'] < df['ema50']) & (df['close'] < df['ema200']), 'strength'] += 2
        
        # RSI Momentum (1 pt)
        df.loc[(df['rsi'] > 55) & (df['rsi'] < 75), 'strength'] += 1
        df.loc[(df['rsi'] < 45) & (df['rsi'] > 25), 'strength'] += 1
        
        # MACD Confirmation (1 pt)
        df.loc[df['macd'] > df['signal_macd'], 'strength'] += 1
        
        # ADX Trend Strength (1 pt)
        df.loc[df['adx'] > 25, 'strength'] += 1
        
        # Volumen / OBV (1 pt)
        if 'volume' in df.columns:
            vol_ma = df['volume'].rolling(window=20).mean()
            df.loc[df['volume'] > vol_ma * 1.2, 'strength'] += 0.5
        df.loc[df['obv'] > df['obv'].shift(1), 'strength'] += 0.5
        
        # Ichimoku confirmation (1 pt)
        df.loc[df['close'] > df[['senkou_a', 'senkou_b']].max(axis=1), 'strength'] += 2
        df.loc[df['close'] < df[['senkou_a', 'senkou_b']].min(axis=1), 'strength'] += 2

        # Divergencias RSI (2 pts - Señal muy fuerte de reversión/continuación)
        # Solo calculamos para las últimas filas para ahorrar tiempo o usamos una ventana
        for i in range(len(df)-1, max(30, len(df)-20), -1):
            if detect_bullish_divergence(df, i):
                df.at[df.index[i], 'strength'] += 2
                break # Solo sumamos a la más reciente
            if detect_bearish_divergence(df, i):
                df.at[df.index[i], 'strength'] += 2
                break
        
        # 4. Generar condiciones base de Compra (Crossover EMA + Trend + Momentum)
        allow_late = self.parameters.get('allow_late_entry', False)
        if isinstance(allow_late, str): allow_late = allow_late.lower() == 'true'
        
        mode = self.parameters.get('strategy_mode', 'balanced').lower()
        
        ema_crossover = (df['ema9'] > df['ema21']) & (df['ema9'].shift(1) <= df['ema21'].shift(1))
        ema_aligned = (df['ema9'] > df['ema21'])
        
        # Filtro de tendencia mandatorio (EMA 200)
        trend_up = (df['close'] > df['ema200'])
        trend_down = (df['close'] < df['ema200'])
        
        # Si permitimos entrada tardía, basta con que estén alineadas. Si no, necesitamos el cruce.
        entry_condition_buy = ema_aligned if allow_late else ema_crossover
        
        # FILTRO DE VOLATILIDAD (Bollinger Squeeze)
        # Queremos comprar cuando NO estamos en un squeeze profundo (queremos expansión)
        # O cuando el precio rompe una zona de squeeze
        vol_filter_buy = True
        if self.parameters.get('use_bollinger_filter', True):
            df = bollinger_bands(df, window=20, num_std=2, generate_signals=False)
            # Evitar comprar si estamos comprimidos (bajo volumen/volatilidad)
            # Comprar solo si hay expansión o no hay squeeze activo
            vol_filter_buy = ~df['bb_squeezing'] | (df['close'] > df['bb_upper'])

        buy_cond = (
            entry_condition_buy & 
            (df['close'] > df['ema50']) &
            trend_up & # FILTRO MANDATORIO EMA 200
            (df['rsi'] > float(self.parameters.get('rsi_buy', 55))) &
            vol_filter_buy
        )
        
        # Si no es entrada tardía, exigimos MACD positivo para mayor seguridad en el cruce inicial
        if not allow_late:
            buy_cond = buy_cond & (df['macd'] > df['signal_macd'])
        
        # 5. Generar condiciones base de Venta
        entry_condition_sell = (df['ema9'] < df['ema21']) & (df['ema9'].shift(1) >= df['ema21'].shift(1))
        
        vol_filter_sell = True
        if self.parameters.get('use_bollinger_filter', True):
            vol_filter_sell = ~df['bb_squeezing'] | (df['close'] < df['bb_lower'])

        sell_cond = (
            entry_condition_sell & 
            (df['close'] < df['ema50']) &
            trend_down & # FILTRO MANDATORIO EMA 200
            (df['rsi'] < float(self.parameters.get('rsi_sell', 45))) &
            vol_filter_sell
        )
        
        # 6. Aplicar filtros según Modo de Estrategia
        if mode == 'conservative':
            min_strength = 6.0
            min_adx = 25.0
        elif mode == 'aggressive':
            min_strength = 2.0
            min_adx = 15.0
        else: # balanced
            min_strength = 4.0
            min_adx = 20.0

        buy_cond = buy_cond & (df['adx'] >= min_adx) & (df['strength'] >= min_strength)
        sell_cond = sell_cond & (df['adx'] >= min_adx) & (df['strength'] >= min_strength)

        # 7. Aplicar filtro de Velas (si está activado)
        if self.parameters.get('use_candles', False):
            # Si permitimos entrada tardía, no forzamos patrón de velas para la COMPRA 
            # (porque los patrones suelen estar al inicio de la tendencia)
            if allow_late:
                bullish_pattern = True
            else:
                bullish_pattern = (df['is_bullish_engulfing'] | df['is_hammer'] | df['is_bullish_engulfing'].shift(1) | df['is_hammer'].shift(1))
            
            buy_cond = buy_cond & bullish_pattern
            
            bearish_pattern = (df['is_bearish_engulfing'] | df['is_shooting_star'] | df['is_bearish_engulfing'].shift(1) | df['is_shooting_star'].shift(1))
            sell_cond = sell_cond & bearish_pattern
        
        # Asignar señales
        df.loc[buy_cond, 'signal'] = 'BUY'
        df.loc[sell_cond, 'signal'] = 'SELL'
        
        # 8. Calcular SL/TP dinámicos
        for idx in df.index[buy_cond]:
            sl, tp = calculate_sl_tp(df.loc[:idx], 'buy', atr_multiplier_sl=self.parameters['atr_sl'], atr_multiplier_tp=self.parameters['atr_tp'])
            df.at[idx, 'stop_loss'] = sl.iloc[-1]
            df.at[idx, 'take_profit'] = tp.iloc[-1]
            
        for idx in df.index[sell_cond]:
            sl, tp = calculate_sl_tp(df.loc[:idx], 'sell', atr_multiplier_sl=self.parameters['atr_sl'], atr_multiplier_tp=self.parameters['atr_tp'])
            df.at[idx, 'stop_loss'] = sl.iloc[-1]
            df.at[idx, 'take_profit'] = tp.iloc[-1]
            
        return df


class GridStrategy(TradingStrategy):
    """
    Estrategia de Grid Trading (Malla).
    Coloca órdenes de compra y venta a intervalos regulares dentro de un rango.
    """
    def __init__(self, parameters=None):
        super().__init__("Grid Trading", parameters)
        default_params = {
            'upper_price': 0,
            'lower_price': 0,
            'grid_levels': 10,
            'amount_per_level': 100, # USD por nivel
            'global_stop_loss': None,
            'global_take_profit': None
        }
        self.parameters = {**default_params, **(parameters or {})}

    def generate_signals(self, df):
        # El Grid no genera señales de entrada tradicionales (BUY/SELL) en cada vela,
        # sino que el motor de simulación maneja la ejecución basada en niveles de precio.
        df['signal'] = 'GRID' 
        return df


class SupertrendStrategy(TradingStrategy):
    """Estrategia basada en Supertrend"""
    def __init__(self, parameters=None):
        super().__init__("Supertrend", parameters)
        # Casting defensivo
        if self.parameters:
            for key in self.parameters:
                try:
                    if isinstance(self.parameters[key], str):
                        if '.' in self.parameters[key]:
                            self.parameters[key] = float(self.parameters[key])
                        else:
                            self.parameters[key] = int(self.parameters[key])
                except:
                    pass

    def generate_signals(self, df):
        # Aplicar indicadores necesarios para el scoring de Supertrend
        df = supertrend(df)
        df = macd(df)
        df = ichimoku_cloud(df)
        df = detect_candlestick_patterns(df)

        # Generar señales (Usa la lógica de scoring de ccxttest1.py integrada a través de generate_signals_from_ccxt)
        df = generate_signals_from_ccxt(df)

        # Convertir señales a formato estándar para el backtester
        df['signal'] = 'HOLD'
        if 'signal_buy_sell' in df.columns:
            df.loc[df['signal_buy_sell'] == 'buy', 'signal'] = 'BUY'
            df.loc[df['signal_buy_sell'] == 'sell', 'signal'] = 'SELL'

        return df


class Backtester:
    """
    Motor de backtesting mejorado que puede trabajar con señales de la BD
    """
    def __init__(self, initial_balance=10000, commission=0.001, risk_per_trade_pct=2.0):
        self.initial_balance = initial_balance
        self.commission = commission  # 0.1% commission por defecto
        self.risk_per_trade_pct = risk_per_trade_pct  # % del balance a arriesgar por trade
        self.results = []

    def run_backtest_from_signals(self, pair_symbol, start_date, end_date, timeframe='1h', signals_queryset=None, min_strength=0, min_adx=0, stop_loss_pct=None, take_profit_pct=None, trailing_stop=False, atr_mult_sl=1.5, atr_mult_tp=3.0):
        """
        Ejecuta backtest usando señales existentes de la base de datos
        
        Args:
            pair_symbol: Símbolo del par (ej: 'ETH/USDT')
            start_date: Fecha de inicio
            end_date: Fecha de fin
            timeframe: Timeframe de las señales (ej: '1h', '15m')
            signals_queryset: QuerySet de TradeSignal (opcional, si no se pasa se obtiene de la BD)
            min_strength: Fuerza mínima de la señal (entero >= 0)
            min_adx: Umbral mínimo de ADX para filtrar señales (0 = sin filtro)
            stop_loss_pct: Porcentaje de stop loss (ej: 2.0 para 2%)
            take_profit_pct: Porcentaje de take profit (ej: 4.0 para 4%)
            trailing_stop: Si se debe aplicar trailing stop
            atr_mult_sl: Multiplicador ATR para Stop Loss
            atr_mult_tp: Multiplicador ATR para Take Profit
        
        Returns:
            dict con resultados del backtest
        """
        try:
            # 1. Obtener el par
            pair = TradingPair.objects.get(symbol=pair_symbol)
            
            # DEBUG: Imprimir parámetros de búsqueda
            print(f"BACKTEST DEBUG: Buscando señales para Par={pair.id}({pair_symbol}), Inicio={start_date}, Fin={end_date}, TF={timeframe}, Fuerza={min_strength}")

            # 2. Obtener señales si no se pasaron
            if signals_queryset is None:
                signals_queryset = TradeSignal.objects.filter(
                    pair=pair,
                    timestamp__gte=start_date,
                    timestamp__lt=end_date,
                    timeframe=timeframe,
                    strength__gte=min_strength
                ).order_by('timestamp')
                
                # Apply ADX filter if specified (filter by stored JSON value)
                if min_adx and min_adx > 0:
                    signals_queryset = signals_queryset.filter(
                        indicators__adx__gte=min_adx
                    )
            
            # DEBUG: Cantidad de señales encontradas
            print(f"BACKTEST DEBUG: Señales encontradas: {signals_queryset.count() if signals_queryset else 0}")
            
            if not signals_queryset.exists():
                return {
                    'error': 'No signals found for the specified period',
                    'initial_balance': self.initial_balance,
                    'final_balance': self.initial_balance,
                    'total_return': 0,
                    'total_trades': 0,
                    'trades': [],
                    'equity_curve': []
                }
            
            # 3. Convertir señales a DataFrame
            signals_data = []
            for signal in signals_queryset:
                data = {
                    'timestamp': signal.timestamp,
                    'signal_type': signal.signal_type,
                    'price': float(signal.price),
                    'strength': signal.strength,
                    'indicator': signal.indicator
                }
                # Unpack dynamic SL/TP from JSON if available
                if signal.indicators:
                    if 'stop_loss' in signal.indicators:
                        data['stop_loss'] = float(signal.indicators['stop_loss'])
                    if 'take_profit' in signal.indicators:
                        data['take_profit'] = float(signal.indicators['take_profit'])
                signals_data.append(data)
            
            df_signals = pd.DataFrame(signals_data)
            df_signals['timestamp'] = pd.to_datetime(df_signals['timestamp'])
            df_signals = df_signals.sort_values('timestamp').reset_index(drop=True)
            
            # 4. Obtener datos OHLCV para el período
            ohlcv_data = OHLCVData.objects.filter(
                pair=pair,
                timestamp__gte=start_date,
                timestamp__lt=end_date,
                timeframe=timeframe
            ).order_by('timestamp')
            
            if ohlcv_data.exists():
                df_ohlcv = pd.DataFrame(list(ohlcv_data.values(
                    'timestamp', 'open', 'high', 'low', 'close', 'volume'
                )))
                df_ohlcv['timestamp'] = pd.to_datetime(df_ohlcv['timestamp'])
                
                # Convertir Decimal a float
                for col in ['open', 'high', 'low', 'close', 'volume']:
                    df_ohlcv[col] = df_ohlcv[col].astype(float)
            else:
                # Si no hay datos OHLCV, crear un DataFrame básico con las señales
                df_ohlcv = df_signals[['timestamp', 'price']].copy()
                df_ohlcv['open'] = df_ohlcv['price']
                df_ohlcv['high'] = df_ohlcv['price'] * 1.001
                df_ohlcv['low'] = df_ohlcv['price'] * 0.999
                df_ohlcv['close'] = df_ohlcv['price']
                df_ohlcv['volume'] = 0
            
            # 5. Combinar señales con datos OHLCV
            signal_cols = ['timestamp', 'signal_type', 'strength']
            if 'stop_loss' in df_signals.columns:
                signal_cols.append('stop_loss')
            if 'take_profit' in df_signals.columns:
                signal_cols.append('take_profit')

            df_combined = pd.merge_asof(
                df_ohlcv.sort_values('timestamp'),
                df_signals[signal_cols].sort_values('timestamp'),
                on='timestamp',
                direction='nearest',
                tolerance=pd.Timedelta('5min')
            )
            
            df_combined['signal'] = df_combined['signal_type'].fillna('HOLD')
            df_combined['signal'] = df_combined['signal'].str.upper()
            
            # 6. Simular trading
            results = self.simulate_trading(
                df_combined, 
                stop_loss_pct=stop_loss_pct, 
                take_profit_pct=take_profit_pct, 
                trailing_stop=trailing_stop,
                atr_multiplier_sl=atr_mult_sl,
                atr_multiplier_tp=atr_mult_tp
            )
            
            # 7. Calcular métricas
            results.update(self.calculate_metrics(df_combined, results))
            
            # 8. Guardar resultados
            self.save_results(
                strategy_name="Signal-Based",
                pair_symbol=pair_symbol,
                start_date=start_date,
                end_date=end_date,
                results=results,
                parameters={
                    'min_strength': min_strength,
                    'min_adx': min_adx,
                    'stop_loss_pct': stop_loss_pct,
                    'take_profit_pct': take_profit_pct,
                    'trailing_stop': trailing_stop,
                    'atr_mult_sl': atr_mult_sl,
                    'atr_mult_tp': atr_mult_tp
                }
            )
            
            return results
            
        except TradingPair.DoesNotExist:
            return {
                'error': f'Trading pair {pair_symbol} not found',
                'initial_balance': self.initial_balance,
                'final_balance': self.initial_balance,
                'total_return': 0,
                'total_trades': 0,
                'trades': [],
                'equity_curve': []
            }
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {
                'error': str(e),
                'initial_balance': self.initial_balance,
                'final_balance': self.initial_balance,
                'total_return': 0,
                'total_trades': 0,
                'trades': [],
                'equity_curve': []
            }

    def run_backtest(self, strategy, pair_symbol, start_date, end_date, timeframe='1m', 
                     stop_loss_pct=None, take_profit_pct=None, trailing_stop=False, 
                     atr_mult_sl=1.5, atr_mult_tp=3.0):
        """Ejecuta un backtest completo con una estrategia específica"""

        # 1. Obtener datos
        df = DataManager.get_or_fetch(pair_symbol, timeframe, start=start_date, end=end_date)
        if df.empty:
            return {'error': f"No data found for {pair_symbol} in the specified range"}

        # Asegurar tipos float para cálculos
        for col in ['open', 'high', 'low', 'close', 'volume']:
            if col in df.columns:
                df[col] = df[col].astype(float)

        # 2. Generar señales usando la estrategia
        df = strategy.generate_signals(df)

        # 3. Simular trading (Seleccionar motor según la estrategia)
        if strategy.name == "Grid Trading":
            results = self.simulate_grid_trading(df, strategy.parameters)
        else:
            results = self.simulate_trading(
                df, 
                stop_loss_pct=stop_loss_pct, 
                take_profit_pct=take_profit_pct, 
                trailing_stop=trailing_stop,
                atr_multiplier_sl=atr_mult_sl,
                atr_multiplier_tp=atr_mult_tp
            )

        # Si hubo un error en la simulación, retornar inmediatamente
        if 'error' in results:
            return results

        # 4. Calcular métricas adicionales
        results.update(self.calculate_metrics(df, results))

        # 5. Guardar resultados
        self.save_results(
            strategy_name=strategy.name,
            pair_symbol=pair_symbol,
            start_date=start_date,
            end_date=end_date,
            results=results,
            parameters=strategy.parameters
        )

        return results

    def simulate_trading(self, df, stop_loss_pct=None, take_profit_pct=None, trailing_stop=False,
                         atr_multiplier_sl=1.5, atr_multiplier_tp=3.0, cooldown_bars=3):
        """Simula ejecución de trades con gestión de riesgo avanzada.
        
        Mejoras v2:
        - Position sizing dinámico: arriesga un % fijo del balance por trade.
        - Cool-down: mínimo N velas entre trades para evitar overtrading.
        """
        balance = self.initial_balance
        position = 0
        trades = []
        equity_curve = []
        entry_price_actual = 0
        sl_price = 0
        tp_price = 0
        max_price_since_entry = 0
        last_sell_bar = -cooldown_bars  # Permite operar desde la primera barra
        bar_counter = 0

        for i, row in df.iterrows():
            current_price = float(row['close'])
            signal = row.get('signal', 'HOLD')
            current_balance = balance + (position * current_price if position > 0 else 0)

            # 1. Verificar Stop Loss o Take Profit si estamos en posición
            if position > 0:
                exit_reason = None
                
                # Priorizar SL/TP dinámicos del DataFrame si existen
                current_sl_price = row.get('stop_loss', sl_price) if not pd.isna(row.get('stop_loss')) else sl_price
                current_tp_price = row.get('take_profit', tp_price) if not pd.isna(row.get('take_profit')) else tp_price

                # Lógica de Trailing Stop
                if trailing_stop and stop_loss_pct:
                    if current_price > max_price_since_entry:
                        max_price_since_entry = current_price
                        new_sl = max_price_since_entry * (1 - stop_loss_pct / 100)
                        if new_sl > current_sl_price:
                            current_sl_price = new_sl
                            sl_price = new_sl

                if current_sl_price and current_price <= current_sl_price:
                    exit_reason = 'STOP_LOSS'
                elif current_tp_price and current_price >= current_tp_price:
                    exit_reason = 'TAKE_PROFIT'
                
                if exit_reason:
                    exit_price = current_price * (1 - self.commission)
                    realized_balance = position * exit_price
                    pnl = realized_balance - trades[-1]['balance_before']
                    pnl_pct = (pnl / trades[-1]['balance_before']) * 100
                    
                    trades.append({
                        'timestamp': row['timestamp'],
                        'action': 'SELL',
                        'reason': exit_reason,
                        'price': current_price,
                        'exit_price': exit_price,
                        'size': position,
                        'balance_after': realized_balance,
                        'pnl': pnl,
                        'pnl_pct': pnl_pct
                    })
                    balance = realized_balance
                    position = 0
                    last_sell_bar = bar_counter
                    bar_counter += 1
                    equity_curve.append({'timestamp': row['timestamp'], 'equity': balance, 'in_position': False})
                    continue

            # 2. Ejecutar señales de entrada (con cool-down)
            in_cooldown = (bar_counter - last_sell_bar) < cooldown_bars
            
            if signal == 'BUY' and position == 0 and not in_cooldown:
                entry_price_actual = current_price * (1 + self.commission)
                
                # ---- POSITION SIZING DINÁMICO ----
                # Calcular SL provisional para determinar el tamaño de posición
                provisional_sl = None
                if 'stop_loss' in row and not pd.isna(row.get('stop_loss')):
                    provisional_sl = float(row['stop_loss'])
                elif stop_loss_pct:
                    provisional_sl = entry_price_actual * (1 - stop_loss_pct / 100)
                
                if provisional_sl and provisional_sl < entry_price_actual:
                    sl_distance = entry_price_actual - provisional_sl
                    risk_amount = balance * (self.risk_per_trade_pct / 100)
                    position = risk_amount / sl_distance  # Unidades a comprar
                    # Cap: no invertir más del 100% del balance disponible
                    max_units = balance / entry_price_actual
                    position = min(position, max_units)
                else:
                    # Sin SL definido: usar el 100% del balance (comportamiento legacy)
                    position = balance / entry_price_actual
                
                sl_price = provisional_sl or 0
                tp_price = 0
                max_price_since_entry = entry_price_actual
                
                if take_profit_pct:
                    tp_price = entry_price_actual * (1 + take_profit_pct / 100)
                if 'take_profit' in row and not pd.isna(row.get('take_profit')):
                    tp_price = float(row['take_profit'])

                balance_before = balance
                cost = position * entry_price_actual
                balance -= cost  # El resto queda como efectivo libre
                
                trades.append({
                    'timestamp': row['timestamp'],
                    'action': 'BUY',
                    'price': current_price,
                    'entry_price': entry_price_actual,
                    'size': position,
                    'strength': row.get('strength', 0),
                    'balance_before': balance_before,
                    'sl_price': sl_price if sl_price else None,
                    'tp_price': tp_price if tp_price else None
                })
                
            elif signal == 'SELL' and position > 0:
                exit_price = current_price * (1 - self.commission)
                proceeds = position * exit_price
                balance += proceeds  # Sumar lo obtenido al efectivo libre
                
                pnl = proceeds - (trades[-1]['size'] * trades[-1]['entry_price'])
                pnl_pct = (pnl / trades[-1]['balance_before']) * 100
                
                trades.append({
                    'timestamp': row['timestamp'],
                    'action': 'SELL',
                    'reason': 'SIGNAL',
                    'price': current_price,
                    'exit_price': exit_price,
                    'size': position,
                    'balance_after': balance,
                    'pnl': pnl,
                    'pnl_pct': pnl_pct
                })
                position = 0
                last_sell_bar = bar_counter

            # Calcular equity actual
            current_equity = balance + (position * current_price if position > 0 else 0)
            equity_curve.append({
                'timestamp': row['timestamp'],
                'equity': current_equity,
                'in_position': position > 0
            })
            bar_counter += 1

        # Calcular métricas finales
        final_price = float(df.iloc[-1]['close'])
        final_balance = balance + (position * final_price if position > 0 else 0)
        total_return = ((final_balance - self.initial_balance) / self.initial_balance) * 100

        return {
            'initial_balance': self.initial_balance,
            'final_balance': final_balance,
            'total_return': total_return,
            'total_trades': len([t for t in trades if t['action'] == 'BUY']),  # Contar solo entradas
            'trades': trades,
            'equity_curve': equity_curve
        }

    def calculate_metrics(self, df, results):
        """Calcula métricas adicionales del backtest"""
        trades = results['trades']
        equity_curve = results.get('equity_curve', [])

        if not trades:
            return {
                'sharpe_ratio': 0,
                'max_drawdown': 0,
                'win_rate': 0,
                'profit_factor': 0,
                'avg_trade': 0,
                'best_trade': 0,
                'worst_trade': 0,
                'total_fees': 0,
                'avg_win': 0,
                'avg_loss': 0,
                'total_wins': 0,
                'total_losses': 0
            }

        # Calcular retornos desde equity curve
        if equity_curve:
            equity_df = pd.DataFrame(equity_curve)
            equity_df['returns'] = equity_df['equity'].pct_change()
            daily_returns = equity_df['returns'].dropna()
        else:
            daily_returns = pd.Series([])

        # Sharpe Ratio (anualizado)
        if len(daily_returns) > 0 and daily_returns.std() > 0:
            sharpe_ratio = (daily_returns.mean() / daily_returns.std()) * np.sqrt(252)
        else:
            sharpe_ratio = 0

        # Calcular drawdown máximo desde equity curve
        if equity_curve:
            equity_values = [e['equity'] for e in equity_curve]
            running_max = np.maximum.accumulate(equity_values)
            drawdown = (np.array(equity_values) - running_max) / running_max
            max_drawdown = drawdown.min() * 100 if len(drawdown) > 0 else 0
        else:
            max_drawdown = 0

        # Calcular métricas de trades
        trade_returns = []
        winning_trades = []
        losing_trades = []
        total_fees = 0

        # Emparejar compras con ventas
        buy_trades = [t for t in trades if t['action'] == 'BUY']
        sell_trades = [t for t in trades if t['action'] == 'SELL']
        
        for i in range(min(len(buy_trades), len(sell_trades))):
            buy_trade = buy_trades[i]
            sell_trade = sell_trades[i]
            
            entry_price = buy_trade['entry_price']
            exit_price = sell_trade['exit_price']
            
            trade_return = ((exit_price - entry_price) / entry_price) * 100
            trade_returns.append(trade_return)
            
            # Calcular fees
            fee_amount = (buy_trade['price'] * buy_trade['size'] * self.commission) + \
                        (sell_trade['price'] * sell_trade['size'] * self.commission)
            total_fees += fee_amount
            
            if trade_return > 0:
                winning_trades.append(trade_return)
            else:
                losing_trades.append(trade_return)

        win_rate = (len(winning_trades) / len(trade_returns)) * 100 if trade_returns else 0
        
        total_wins = sum(winning_trades) if winning_trades else 0
        total_losses = abs(sum(losing_trades)) if losing_trades else 0
        profit_factor = total_wins / total_losses if total_losses > 0 else (float('inf') if total_wins > 0 else 0)

        return {
            'sharpe_ratio': round(sharpe_ratio, 2),
            'max_drawdown': round(max_drawdown, 2),
            'win_rate': round(win_rate, 2),
            'profit_factor': round(profit_factor, 2),
            'avg_trade': round(sum(trade_returns) / len(trade_returns), 2) if trade_returns else 0,
            'best_trade': round(max(trade_returns), 2) if trade_returns else 0,
            'worst_trade': round(min(trade_returns), 2) if trade_returns else 0,
            'total_fees': round(total_fees, 2),
            'avg_win': round(sum(winning_trades) / len(winning_trades), 2) if winning_trades else 0,
            'avg_loss': round(sum(losing_trades) / len(losing_trades), 2) if losing_trades else 0,
            'total_wins': len(winning_trades),
            'total_losses': len(losing_trades)
        }

    def save_results(self, strategy_name, pair_symbol, start_date, end_date, results, parameters=None):
        """Guarda resultados en BD"""
        try:
            pair = TradingPair.objects.get(symbol=pair_symbol)

            BacktestResult.objects.create(
                name=f"{strategy_name}_{start_date.date()}_{end_date.date()}",
                pair=pair,
                start_date=start_date,
                end_date=end_date,
                strategy_name=strategy_name,
                parameters=parameters or {},
                total_return=results['total_return'],
                total_trades=results['total_trades'],
                win_rate=results.get('win_rate', 0),
                max_drawdown=results.get('max_drawdown', 0),
                sharpe_ratio=results.get('sharpe_ratio', 0),
                profit_factor=results.get('profit_factor', 0),
                avg_trade=results.get('avg_trade', 0),
                best_trade=results.get('best_trade', 0),
                worst_trade=results.get('worst_trade', 0),
                total_fees=results.get('total_fees', 0)
            )
            return True
        except Exception as e:
            print(f"Error saving backtest results: {e}")
            import traceback
            traceback.print_exc()
            return False

    def generate_equity_chart(self, results):
        """Genera gráfico de equity curve"""
        equity_curve = results.get('equity_curve', [])
        if not equity_curve:
            return None
        
        df_equity = pd.DataFrame(equity_curve)
        
        fig = go.Figure()
        
        # Línea de equity
        fig.add_trace(go.Scatter(
            x=df_equity['timestamp'],
            y=df_equity['equity'],
            mode='lines',
            name='Equity',
            line=dict(color='#2ecc71', width=2)
        ))
        
        # Línea de balance inicial
        fig.add_trace(go.Scatter(
            x=df_equity['timestamp'],
            y=[self.initial_balance] * len(df_equity),
            mode='lines',
            name='Initial Balance',
            line=dict(color='#95a5a6', width=1, dash='dash')
        ))
        
        fig.update_layout(
            title='Equity Curve',
            xaxis_title='Date',
            yaxis_title='Balance (USDT)',
            template='plotly_white',
            hovermode='x unified',
            height=400
        )
        
        return fig.to_html(full_html=False, include_plotlyjs='cdn')

    def generate_trades_chart(self, results, df_price=None):
        """Genera gráfico con trades marcados"""
        trades = results.get('trades', [])
        if not trades:
            return None
        
        fig = go.Figure()
        
        # Si hay datos de precio, mostrar candlestick
        if df_price is not None and not df_price.empty:
            fig.add_trace(go.Candlestick(
                x=df_price['timestamp'],
                open=df_price['open'],
                high=df_price['high'],
                low=df_price['low'],
                close=df_price['close'],
                name='Price'
            ))
        
        # Marcar compras
        buy_trades = [t for t in trades if t['action'] == 'BUY']
        if buy_trades:
            fig.add_trace(go.Scatter(
                x=[t['timestamp'] for t in buy_trades],
                y=[t['price'] for t in buy_trades],
                mode='markers',
                name='Buy',
                marker=dict(color='green', size=12, symbol='triangle-up')
            ))
        
        # Marcar ventas
        sell_trades = [t for t in trades if t['action'] == 'SELL']
        if sell_trades:
            fig.add_trace(go.Scatter(
                x=[t['timestamp'] for t in sell_trades],
                y=[t['price'] for t in sell_trades],
                mode='markers',
                name='Sell',
                marker=dict(color='red', size=12, symbol='triangle-down')
            ))
        
        fig.update_layout(
            title='Trades on Chart',
            xaxis_title='Date',
            yaxis_title='Price (USDT)',
            template='plotly_white',
            hovermode='x unified',
            height=500
        )
        
        return fig.to_html(full_html=False, include_plotlyjs='cdn')

    def simulate_grid_trading(self, df, params):
        """
        Simula una estrategia de Grid Trading con múltiples niveles abiertos simultáneamente.
        """
        upper = float(params.get('upper_price', 0))
        lower = float(params.get('lower_price', 0))
        levels_count = int(params.get('grid_levels', 10))
        amount_per_level = float(params.get('amount_per_level', 100))
        stop_loss_price = params.get('global_stop_loss')
        if stop_loss_price: stop_loss_price = float(stop_loss_price)

        # Validaciones básicas
        if upper <= lower or levels_count < 2:
            return {'error': 'Configuración de Grid inválida (Rango o niveles incorrectos)'}

        # Calcular niveles (Malla aritmética)
        grid_step = (upper - lower) / (levels_count - 1)
        grid_levels = [lower + i * grid_step for i in range(levels_count)]
        
        balance = self.initial_balance
        active_positions = [] # [{'entry_price': f, 'size': f, 'target_tp': f}]
        trades = []
        equity_curve = []
        is_stopped = False
        
        for i, row in df.iterrows():
            current_price = float(row['close'])
            
            if is_stopped:
                # Si se detuvo por SL Global, solo registramos la curva de equity (balance estático)
                equity_curve.append({'timestamp': row['timestamp'], 'equity': balance})
                continue

            # 1. Verificar Stop Loss Global (Riesgo máximo)
            if stop_loss_price and current_price <= stop_loss_price and active_positions:
                for pos in active_positions:
                    exit_price = current_price * (1 - self.commission)
                    balance += pos['size'] * exit_price
                    trades.append({
                        'timestamp': row['timestamp'],
                        'action': 'SELL',
                        'reason': 'GLOBAL_STOP_LOSS',
                        'price': current_price,
                        'exit_price': exit_price,
                        'size': pos['size'],
                        'pnl': (exit_price - pos['entry_price']) * pos['size']
                    })
                active_positions = []
                is_stopped = True # Detener estrategia tras el desastre
                continue

            # 2. Verificar Cierres (Take Profit de cada nivel)
            remaining_positions = []
            for pos in active_positions:
                if current_price >= pos['target_tp']:
                    exit_price = current_price * (1 - self.commission)
                    balance += pos['size'] * exit_price
                    trades.append({
                        'timestamp': row['timestamp'],
                        'action': 'SELL',
                        'reason': 'GRID_TAKE_PROFIT',
                        'price': current_price,
                        'entry_price': pos['entry_price'],
                        'exit_price': exit_price,
                        'size': pos['size'],
                        'pnl': (exit_price - pos['entry_price']) * pos['size']
                    })
                else:
                    remaining_positions.append(pos)
            active_positions = remaining_positions

            # 3. Verificar Entradas (Nuevas compras en niveles)
            # Solo comprar si estamos por encima del límite inferior (dentro de la malla)
            if current_price >= (lower - grid_step * 0.5):
                for level in grid_levels:
                    # Compramos si el precio baja al nivel O está por debajo de él
                    if current_price <= level:
                        # No comprar si ya hay una posición abierta en este exacto nivel
                        already_bought = any(abs(pos['entry_price'] - level) < (grid_step * 0.1) for pos in active_positions)
                        
                        if not already_bought and balance >= amount_per_level:
                            entry_price = current_price * (1 + self.commission)
                            size = amount_per_level / entry_price
                            balance -= amount_per_level
                            
                            active_positions.append({
                                'entry_price': level,
                                'actual_entry': entry_price,
                                'size': size,
                                'target_tp': level + grid_step
                            })
                            
                            trades.append({
                                'timestamp': row['timestamp'],
                                'action': 'BUY',
                                'reason': 'GRID_BUY',
                                'price': current_price,
                                'entry_price': entry_price,
                                'size': size
                            })

            # Equity Curve: Balance Efectivo + Valor de mercado de posiciones abiertas
            unrealized_value = sum(pos['size'] * current_price for pos in active_positions)
            current_equity = balance + unrealized_value
            equity_curve.append({
                'timestamp': row['timestamp'],
                'equity': current_equity
            })

        return {
            'total_return': ((equity_curve[-1]['equity'] / self.initial_balance) - 1) * 100 if equity_curve else 0,
            'total_trades': len(trades),
            'trades': trades,
            'equity_curve': equity_curve,
            'final_balance': equity_curve[-1]['equity'] if equity_curve else balance
        }
