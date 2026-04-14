#!/usr/bin/env python3
"""
Test optimized strategy with real data.
"""
import os
import sys
import django
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')
django.setup()

from dashboard.optimized_strategies import OptimizedDayTradingStrategy
from dashboard.data_service import DataManager

def test_bot_params(bot_params, pair_symbol='SOL/USDT', timeframe='1h', days=10):
    """Test strategy with given parameters."""
    print(f'\nTesting with {len(bot_params)} parameters')
    
    # Fetch recent data
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    df = DataManager.get_or_fetch(
        pair_symbol=pair_symbol,
        timeframe=timeframe,
        start=start_date,
        end=end_date,
        limit=500
    )
    if df.empty:
        print('No data fetched')
        return
    
    print(f'Data shape: {df.shape}')
    
    # Create strategy
    strategy = OptimizedDayTradingStrategy(parameters=bot_params)
    
    # Generate signals
    try:
        df_signals = strategy.generate_signals(df.copy())
        print('Signal generation successful')
        
        # Count signals
        buy_signals = (df_signals['signal'] == 'BUY').sum()
        sell_signals = (df_signals['signal'] == 'SELL').sum()
        print(f'Buy signals: {buy_signals}, Sell signals: {sell_signals}')
        
        if buy_signals > 0 or sell_signals > 0:
            # Show some signal rows
            signals = df_signals[df_signals['signal'].isin(['BUY', 'SELL'])]
            print(f'Sample signals:')
            for idx, row in signals.head(3).iterrows():
                print(f"  {row['signal']} at {row['close']:.4f}, RSI {row.get('rsi', 0):.1f}, SL {row.get('stop_loss', 0):.4f}")
        else:
            print('No signals generated. Checking indicators...')
            # Check if indicators calculated
            print(f"Indicators present: {list(df_signals.columns)}")
            # Check typical values
            if 'rsi' in df_signals.columns:
                print(f"RSI range: {df_signals['rsi'].min():.1f} - {df_signals['rsi'].max():.1f}")
            if 'adx' in df_signals.columns:
                print(f"ADX range: {df_signals['adx'].min():.1f} - {df_signals['adx'].max():.1f}")
            if 'regime' in df_signals.columns:
                print(f"Regime counts: {df_signals['regime'].value_counts().to_dict()}")
                
    except Exception as e:
        print(f'Error generating signals: {e}')
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    # Test with default optimized parameters
    default_params = {
        'ema_fast': 9,
        'ema_slow': 21,
        'ema_trend': 200,
        'rsi_period': 14,
        'rsi_upper_dynamic': True,
        'rsi_lower_dynamic': True,
        'rsi_upper_static': 60,
        'rsi_lower_static': 40,
        'atr_period': 14,
        'atr_sl_multiplier': 1.5,
        'atr_tp_multiplier': 3.0,
        'use_volume_filter': True,
        'volume_ma_period': 20,
        'min_adx': 20,
        'risk_per_trade_pct': 1.0,
        'max_positions': 3,
        'cooldown_bars': 5,
        'market_regime_filter': True,
    }
    print('=== Testing default optimized parameters ===')
    test_bot_params(default_params)
    
    # Test with migrated bot parameters (Solbottrend)
    from dashboard.models import LiveBot
    bot = LiveBot.objects.get(id=7)
    print('\n=== Testing migrated bot parameters (Solbottrend) ===')
    test_bot_params(bot.parameters, pair_symbol='SOL/USDT')
    
    # Test with ETHUpperbot parameters
    bot10 = LiveBot.objects.get(id=10)
    print('\n=== Testing migrated bot parameters (ETHUpperbot) ===')
    test_bot_params(bot10.parameters, pair_symbol='ETH/USDT')