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


class SupertrendStrategy(TradingStrategy):
    """Estrategia basada en Supertrend"""
    def __init__(self, parameters=None):
        super().__init__("Supertrend", parameters)

    def generate_signals(self, df):
        # Aplicar indicadores
        df = supertrend(df)
        df = macd(df)
        df = enhanced_bollinger_bands(df, window=20, num_std=2, strategy='all')
        df = ichimoku_cloud(df)

        # Generar señales
        df = generate_signals_from_ccxt(df)

        # Convertir señales a formato estándar
        df['signal'] = 'HOLD'
        df.loc[df['signal_buy_sell'] == 'buy', 'signal'] = 'BUY'
        df.loc[df['signal_buy_sell'] == 'sell', 'signal'] = 'SELL'

        return df


class Backtester:
    """
    Motor de backtesting mejorado que puede trabajar con señales de la BD
    """
    def __init__(self, initial_balance=10000, commission=0.001):
        self.initial_balance = initial_balance
        self.commission = commission  # 0.1% commission por defecto
        self.results = []

    def run_backtest_from_signals(self, pair_symbol, start_date, end_date, signals_queryset=None):
        """
        Ejecuta backtest usando señales existentes de la base de datos
        
        Args:
            pair_symbol: Símbolo del par (ej: 'ETH/USDT')
            start_date: Fecha de inicio
            end_date: Fecha de fin
            signals_queryset: QuerySet de TradeSignal (opcional, si no se pasa se obtiene de la BD)
        
        Returns:
            dict con resultados del backtest
        """
        try:
            # 1. Obtener el par
            pair = TradingPair.objects.get(symbol=pair_symbol)
            
            # 2. Obtener señales si no se pasaron
            if signals_queryset is None:
                signals_queryset = TradeSignal.objects.filter(
                    pair=pair,
                    timestamp__gte=start_date,
                    timestamp__lte=end_date
                ).order_by('timestamp')
            
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
                signals_data.append({
                    'timestamp': signal.timestamp,
                    'signal_type': signal.signal_type,
                    'price': float(signal.price),
                    'strength': signal.strength,
                    'indicator': signal.indicator
                })
            
            df_signals = pd.DataFrame(signals_data)
            df_signals['timestamp'] = pd.to_datetime(df_signals['timestamp'])
            df_signals = df_signals.sort_values('timestamp').reset_index(drop=True)
            
            # 4. Obtener datos OHLCV para el período
            ohlcv_data = OHLCVData.objects.filter(
                pair=pair,
                timestamp__gte=start_date,
                timestamp__lte=end_date
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
            df_combined = pd.merge_asof(
                df_ohlcv.sort_values('timestamp'),
                df_signals[['timestamp', 'signal_type', 'strength']].sort_values('timestamp'),
                on='timestamp',
                direction='nearest',
                tolerance=pd.Timedelta('5min')
            )
            
            df_combined['signal'] = df_combined['signal_type'].fillna('HOLD')
            df_combined['signal'] = df_combined['signal'].str.upper()
            
            # 6. Simular trading
            results = self.simulate_trading(df_combined)
            
            # 7. Calcular métricas
            results.update(self.calculate_metrics(df_combined, results))
            
            # 8. Guardar resultados
            self.save_results(
                strategy_name="Signal-Based",
                pair_symbol=pair_symbol,
                start_date=start_date,
                end_date=end_date,
                results=results
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

    def run_backtest(self, strategy, pair_symbol, start_date, end_date, timeframe='1m'):
        """Ejecuta un backtest completo con una estrategia específica"""

        # 1. Obtener datos
        df = DataManager.get_or_fetch(pair_symbol, timeframe, start=start_date, end=end_date)
        if df.empty:
            raise ValueError(f"No data found for {pair_symbol} in the specified range")

        # 2. Generar señales usando la estrategia
        df = strategy.generate_signals(df)

        # 3. Simular trading
        results = self.simulate_trading(df)

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

    def simulate_trading(self, df):
        """Simula ejecución de trades"""
        balance = self.initial_balance
        position = 0
        trades = []
        equity_curve = []
        entry_price_actual = 0

        for i, row in df.iterrows():
            current_price = float(row['close'])
            signal = row.get('signal', 'HOLD')
            
            # Aplicar comisión en cada trade
            if signal == 'BUY' and position == 0:
                # Comprar
                entry_price_actual = current_price * (1 + self.commission)
                position = balance / entry_price_actual
                balance = 0
                trades.append({
                    'timestamp': row['timestamp'],
                    'action': 'BUY',
                    'price': current_price,
                    'entry_price': entry_price_actual,
                    'size': position,
                    'balance_before': self.initial_balance if len(trades) == 0 else trades[-1].get('balance_after', balance)
                })
                
            elif signal == 'SELL' and position > 0:
                # Vender
                exit_price = current_price * (1 - self.commission)
                balance = position * exit_price
                
                # Calcular P&L del trade
                pnl = balance - (trades[-1]['balance_before'] if trades else self.initial_balance)
                pnl_pct = (pnl / (trades[-1]['balance_before'] if trades else self.initial_balance)) * 100
                
                trades.append({
                    'timestamp': row['timestamp'],
                    'action': 'SELL',
                    'price': current_price,
                    'exit_price': exit_price,
                    'size': position,
                    'balance_after': balance,
                    'pnl': pnl,
                    'pnl_pct': pnl_pct
                })
                position = 0

            # Calcular equity actual
            current_equity = balance + (position * current_price if position > 0 else 0)
            equity_curve.append({
                'timestamp': row['timestamp'],
                'equity': current_equity,
                'in_position': position > 0
            })

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
