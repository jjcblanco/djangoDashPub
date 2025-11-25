import pandas as pd
import numpy as np
from django.utils import timezone
from .models import BacktestResult, TradingPair
from .data_service import DataManager

class Backtester:
    def __init__(self, initial_balance=10000):
        self.initial_balance = initial_balance
        self.results = []
    
    def run_backtest(self, strategy, pair_symbol, start_date, end_date, timeframe='1m'):
        """Ejecuta un backtest completo"""
        
        # 1. Obtener datos
        df = DataManager.get_historical_data(pair_symbol, start_date, end_date, timeframe)
        if df.empty:
            raise ValueError(f"No data found for {pair_symbol} in the specified range")
        
        # 2. Calcular indicadores
        df = self.calculate_indicators(df)
        
        # 3. Generar señales
        df = strategy.generate_signals(df)
        
        # 4. Simular trading
        results = self.simulate_trading(df)
        
        # 5. Guardar resultados
        self.save_results(strategy, pair_symbol, start_date, end_date, results)
        
        return results
    
    def calculate_indicators(self, df):
        """Calcula indicadores técnicos"""
        # Ichimoku
        high_9 = df['high'].rolling(window=9).max()
        low_9 = df['low'].rolling(window=9).min()
        df['tenkan'] = (high_9 + low_9) / 2
        
        high_26 = df['high'].rolling(window=26).max()
        low_26 = df['low'].rolling(window=26).min()
        df['kijun'] = (high_26 + low_26) / 2
        
        # RSI
        df['rsi'] = self.calculate_rsi(df['close'])
        
        # Bollinger Bands
        df['sma_20'] = df['close'].rolling(window=20).mean()
        df['std_20'] = df['close'].rolling(window=20).std()
        df['bollinger_upper'] = df['sma_20'] + (df['std_20'] * 2)
        df['bollinger_lower'] = df['sma_20'] - (df['std_20'] * 2)
        
        return df
    
    def calculate_rsi(self, prices, period=14):
        """Calcula RSI"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def simulate_trading(self, df):
        """Simula ejecución de trades"""
        balance = self.initial_balance
        position = 0
        trades = []
        
        for i, row in df.iterrows():
            if row['signal'] == 'BUY' and position == 0:
                # Comprar
                position = balance / row['close']
                balance = 0
                trades.append({
                    'timestamp': row['timestamp'],
                    'action': 'BUY',
                    'price': row['close'],
                    'size': position
                })
            elif row['signal'] == 'SELL' and position > 0:
                # Vender
                balance = position * row['close']
                trades.append({
                    'timestamp': row['timestamp'],
                    'action': 'SELL',
                    'price': row['close'],
                    'size': position
                })
                position = 0
        
        # Calcular métricas
        final_balance = balance + (position * df.iloc[-1]['close'] if position > 0 else balance)
        total_return = (final_balance - self.initial_balance) / self.initial_balance * 100
        
        return {
            'initial_balance': self.initial_balance,
            'final_balance': final_balance,
            'total_return': total_return,
            'total_trades': len(trades),
            'trades': trades
        }
    
    def save_results(self, strategy, pair_symbol, start_date, end_date, results):
        """Guarda resultados en BD"""
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
            win_rate=self.calculate_win_rate(results['trades']),
            max_drawdown=self.calculate_max_drawdown(results['trades'])
        )