import pandas as pd
import numpy as np
from django.utils import timezone
from .models import BacktestResult, TradingPair, TradeSignal
from .data_service import DataManager
from .indicadores import *
from .ccxttest1 import signals as generate_signals_from_ccxt

class TradingStrategy:
    """Clase base para estrategias de trading"""
    def __init__(self, name, parameters=None):
        self.name = name
        self.parameters = parameters or {}

    def generate_signals(self, df):
        """Método a implementar por cada estrategia"""
        raise NotImplementedError("Subclasses must implement generate_signals")

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
    def __init__(self, initial_balance=10000, commission=0.001):
        self.initial_balance = initial_balance
        self.commission = commission  # 0.1% commission
        self.results = []

    def run_backtest(self, strategy, pair_symbol, start_date, end_date, timeframe='1m'):
        """Ejecuta un backtest completo"""

        # 1. Obtener datos
        df = DataManager.get_historical_data(pair_symbol, start_date, end_date, timeframe)
        if df.empty:
            raise ValueError(f"No data found for {pair_symbol} in the specified range")

        # 2. Generar señales usando la estrategia
        df = strategy.generate_signals(df)

        # 3. Simular trading
        results = self.simulate_trading(df)

        # 4. Calcular métricas adicionales
        results.update(self.calculate_metrics(df, results))

        # 5. Guardar resultados
        self.save_results(strategy, pair_symbol, start_date, end_date, results)

        return results

    def simulate_trading(self, df):
        """Simula ejecución de trades"""
        balance = self.initial_balance
        position = 0
        trades = []
        equity_curve = []

        for i, row in df.iterrows():
            # Aplicar comisión en cada trade
            if row['signal'] == 'BUY' and position == 0:
                # Comprar
                entry_price = row['close'] * (1 + self.commission)
                position = balance / entry_price
                balance = 0
                trades.append({
                    'timestamp': row['timestamp'],
                    'action': 'BUY',
                    'price': row['close'],
                    'entry_price': entry_price,
                    'size': position
                })
            elif row['signal'] == 'SELL' and position > 0:
                # Vender
                exit_price = row['close'] * (1 - self.commission)
                balance = position * exit_price
                trades.append({
                    'timestamp': row['timestamp'],
                    'action': 'SELL',
                    'price': row['close'],
                    'exit_price': exit_price,
                    'size': position
                })
                position = 0

            # Calcular equity actual
            current_equity = balance + (position * row['close'] if position > 0 else 0)
            equity_curve.append({
                'timestamp': row['timestamp'],
                'equity': current_equity
            })

        # Calcular métricas finales
        final_balance = balance + (position * df.iloc[-1]['close'] if position > 0 else balance)
        total_return = (final_balance - self.initial_balance) / self.initial_balance * 100

        return {
            'initial_balance': self.initial_balance,
            'final_balance': final_balance,
            'total_return': total_return,
            'total_trades': len(trades),
            'trades': trades,
            'equity_curve': equity_curve
        }

    def calculate_metrics(self, df, results):
        """Calcula métricas adicionales del backtest"""
        trades = results['trades']

        if not trades:
            return {
                'sharpe_ratio': 0,
                'max_drawdown': 0,
                'win_rate': 0,
                'profit_factor': 0,
                'avg_trade': 0,
                'best_trade': 0,
                'worst_trade': 0,
                'total_fees': 0
            }

        # Calcular retornos diarios
        df['returns'] = df['close'].pct_change()
        daily_returns = df['returns'].dropna()

        # Sharpe Ratio (anualizado)
        if len(daily_returns) > 0 and daily_returns.std() > 0:
            sharpe_ratio = (daily_returns.mean() / daily_returns.std()) * np.sqrt(252)
        else:
            sharpe_ratio = 0

        # Calcular drawdown máximo
        cumulative = (1 + daily_returns).cumprod()
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max
        max_drawdown = drawdown.min() * 100 if len(drawdown) > 0 else 0

        # Calcular métricas de trades
        trade_returns = []
        winning_trades = 0
        losing_trades = 0
        total_fees = 0

        for i in range(0, len(trades), 2):
            if i + 1 < len(trades):
                buy_trade = trades[i]
                sell_trade = trades[i + 1]

                if buy_trade['action'] == 'BUY' and sell_trade['action'] == 'SELL':
                    entry_price = buy_trade['price'] * (1 + self.commission)  # Fee on entry
                    exit_price = sell_trade['price'] * (1 - self.commission)   # Fee on exit

                    trade_return = (exit_price - entry_price) / entry_price * 100
                    trade_returns.append(trade_return)

                    fee_amount = (buy_trade['price'] * buy_trade['size'] * self.commission) + \
                               (sell_trade['price'] * sell_trade['size'] * self.commission)
                    total_fees += fee_amount

                    if trade_return > 0:
                        winning_trades += 1
                    else:
                        losing_trades += 1

        win_rate = (winning_trades / len(trade_returns)) * 100 if trade_returns else 0
        profit_factor = abs(sum(r for r in trade_returns if r > 0) / sum(r for r in trade_returns if r < 0)) if any(r < 0 for r in trade_returns) else float('inf')

        return {
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown,
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'avg_trade': sum(trade_returns) / len(trade_returns) if trade_returns else 0,
            'best_trade': max(trade_returns) if trade_returns else 0,
            'worst_trade': min(trade_returns) if trade_returns else 0,
            'total_fees': total_fees
        }

    def calculate_win_rate(self, trades):
        """Calcula el porcentaje de trades ganadores"""
        if not trades or len(trades) < 2:
            return 0

        winning_trades = 0
        total_trades = 0

        for i in range(0, len(trades), 2):
            if i + 1 < len(trades):
                buy_trade = trades[i]
                sell_trade = trades[i + 1]

                if buy_trade['action'] == 'BUY' and sell_trade['action'] == 'SELL':
                    entry_price = buy_trade['price']
                    exit_price = sell_trade['price']
                    trade_return = (exit_price - entry_price) / entry_price * 100

                    if trade_return > 0:
                        winning_trades += 1
                    total_trades += 1

        return (winning_trades / total_trades) * 100 if total_trades > 0 else 0

    def calculate_max_drawdown(self, trades):
        """Calcula el máximo drawdown"""
        if not trades:
            return 0

        # Para simplificar, calculamos drawdown basado en equity curve
        # En una implementación real, usaríamos precios de cierre
        return 0  # Placeholder - implementar lógica completa según necesidad

    def save_results(self, strategy, pair_symbol, start_date, end_date, results):
        """Guarda resultados en BD"""
        try:
            pair = TradingPair.objects.get(symbol=pair_symbol)

            BacktestResult.objects.create(
                name=f"{strategy.name}_{start_date.date()}_{end_date.date()}",
                pair=pair,
                start_date=start_date,
                end_date=end_date,
                strategy_name=strategy.name,
                parameters=strategy.parameters,
                total_return=results['total_return'],
                total_trades=results['total_trades'],
                win_rate=results.get('win_rate', 0),
                max_drawdown=results.get('max_drawdown', 0),
                sharpe_ratio=results.get('sharpe_ratio', 0),
                profit_factor=results.get('profit_factor', 0)
            )
            return True
        except Exception as e:
            print(f"Error saving backtest results: {e}")
            return False
