#!/usr/bin/env python3
"""
Backtest optimized DayTradingStrategy vs original.
"""
import os
import sys
import django
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')
django.setup()

from dashboard.backtester import Backtester, DayTradingStrategy as OriginalDayTradingStrategy
from dashboard.optimized_strategies import OptimizedDayTradingStrategy
from dashboard.data_service import DataManager

def fetch_historical_data(pair_symbol, timeframe='1h', days=30):
    """Fetch historical data for backtesting."""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    print(f"Fetching {pair_symbol} data from {start_date.date()} to {end_date.date()} ({timeframe})")
    
    df = DataManager.get_or_fetch(
        pair_symbol=pair_symbol,
        timeframe=timeframe,
        start=start_date,
        end=end_date,
        limit=1000
    )
    
    if df.empty:
        print(f"[WARNING] No data found for {pair_symbol}. Trying to fetch from exchange...")
        # Try direct exchange fetch
        from dashboard.ccxttest1 import historical_fetch_ohlcv
        bars = historical_fetch_ohlcv(pair_symbol, timeframe=timeframe, limit=1000)
        if bars:
            df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            print(f"Fetched {len(df)} bars from exchange")
        else:
            raise ValueError(f"No data available for {pair_symbol}")
    
    print(f"Data shape: {df.shape}")
    print(f"Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
    
    return df

def run_strategy_backtest(strategy, strategy_name, pair_symbol, df, initial_balance=10000):
    """Run backtest for a given strategy."""
    print(f"\n{'='*60}")
    print(f"Backtesting: {strategy_name}")
    print(f"{'='*60}")
    
    backtester = Backtester(initial_balance=initial_balance, commission=0.001)
    
    # Use the last 30 days of data
    results = backtester.run_backtest(
        strategy=strategy,
        pair_symbol=pair_symbol,
        start_date=df['timestamp'].min(),
        end_date=df['timestamp'].max(),
        timeframe='1h',  # Doesn't matter as we already have df
        stop_loss_pct=2.0,  # 2% stop loss
        take_profit_pct=4.0, # 4% take profit (2:1 RR)
        trailing_stop=False,
        atr_mult_sl=1.5,
        atr_mult_tp=3.0
    )
    
    if 'error' in results:
        print(f"[ERROR] Error: {results['error']}")
        return None
    
    return results

def print_results(results, strategy_name):
    """Print backtest results."""
    print(f"\n[RESULTS] {strategy_name}")
    print(f"  Final Balance:     ${results['final_balance']:,.2f}")
    print(f"  Total Return:      {results['total_return']:.2f}%")
    print(f"  Total Trades:      {results['total_trades']}")
    print(f"  Win Rate:          {results.get('win_rate', 0):.2f}%")
    print(f"  Sharpe Ratio:      {results.get('sharpe_ratio', 0):.2f}")
    print(f"  Max Drawdown:      {results.get('max_drawdown', 0):.2f}%")
    print(f"  Profit Factor:     {results.get('profit_factor', 0):.2f}")
    print(f"  Avg Trade:         {results.get('avg_trade', 0):.2f}%")
    print(f"  Best Trade:        {results.get('best_trade', 0):.2f}%")
    print(f"  Worst Trade:       {results.get('worst_trade', 0):.2f}%")
    print(f"  Total Fees:        ${results.get('total_fees', 0):.2f}")
    
    # Show trades summary
    trades = results.get('trades', [])
    if trades:
        buy_trades = [t for t in trades if t['action'] == 'BUY']
        sell_trades = [t for t in trades if t['action'] == 'SELL']
        profitable = [t for t in trades if 'pnl' in t and t.get('pnl', 0) > 0]
        
        print(f"  Buy Signals:       {len(buy_trades)}")
        print(f"  Sell Signals:      {len(sell_trades)}")
        print(f"  Profitable Trades: {len(profitable)}/{len(sell_trades)}")
        
        # Show first 3 trades
        print(f"\n  Sample Trades:")
        for i, trade in enumerate(trades[:3]):
            action = trade['action']
            price = trade.get('price', 0)
            timestamp = trade.get('timestamp', '')
            if 'pnl' in trade:
                pnl = trade['pnl']
                pnl_pct = trade.get('pnl_pct', 0)
                print(f"    {i+1}. {action} @ ${price:.4f} | PnL: ${pnl:.2f} ({pnl_pct:.2f}%)")
            else:
                print(f"    {i+1}. {action} @ ${price:.4f}")

def compare_strategies(pair_symbol='SOL/USDT', timeframe='1h', days=60):
    """Compare original vs optimized strategy."""
    print("="*70)
    print("CRYPTO TRADING DASHBOARD - STRATEGY BACKTEST COMPARISON")
    print("="*70)
    
    # Fetch data
    try:
        df = fetch_historical_data(pair_symbol, timeframe, days)
    except Exception as e:
        print(f"[ERROR] Failed to fetch data: {e}")
        return
    
    # Define strategies
    original_params = {
        'ema_fast': 9,
        'ema_med': 21,
        'ema_slow': 50,
        'ema_trend': 200,
        'rsi_period': 14,
        'rsi_buy': 55,
        'rsi_sell': 45,
        'atr_sl': 1.5,
        'atr_tp': 3.0,
        'use_candles': True,
        'min_strength': 4,
        'min_adx': 20,
        'strategy_mode': 'balanced',
        'use_bollinger_filter': True,
        'cooldown_bars': 3,
        'risk_per_trade_pct': 2.0
    }
    
    optimized_params = {
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
        'market_regime_filter': True
    }
    
    original_strategy = OriginalDayTradingStrategy(original_params)
    optimized_strategy = OptimizedDayTradingStrategy(optimized_params)
    
    # Run backtests
    results_original = run_strategy_backtest(
        original_strategy, "Original DayTradingStrategy", pair_symbol, df, 10000
    )
    
    results_optimized = run_strategy_backtest(
        optimized_strategy, "Optimized DayTradingStrategy", pair_symbol, df, 10000
    )
    
    # Print comparison
    if results_original and results_optimized:
        print("\n" + "="*70)
        print("STRATEGY COMPARISON")
        print("="*70)
        
        print("\nORIGINAL STRATEGY:")
        print_results(results_original, "Original")
        
        print("\nOPTIMIZED STRATEGY:")
        print_results(results_optimized, "Optimized")
        
        # Comparison metrics
        print("\n" + "="*70)
        print("IMPROVEMENT ANALYSIS")
        print("="*70)
        
        metrics = [
            ('Total Return', results_original['total_return'], results_optimized['total_return'], '%'),
            ('Win Rate', results_original.get('win_rate', 0), results_optimized.get('win_rate', 0), '%'),
            ('Sharpe Ratio', results_original.get('sharpe_ratio', 0), results_optimized.get('sharpe_ratio', 0), ''),
            ('Max Drawdown', results_original.get('max_drawdown', 0), results_optimized.get('max_drawdown', 0), '%'),
            ('Profit Factor', results_original.get('profit_factor', 0), results_optimized.get('profit_factor', 0), ''),
            ('Total Trades', results_original['total_trades'], results_optimized['total_trades'], '')
        ]
        
        for name, orig, opt, unit in metrics:
            diff = opt - orig
            diff_pct = (diff / abs(orig) * 100) if orig != 0 else 0
            arrow = "+" if diff > 0 else "-" if diff < 0 else "="
            trend = "IMPROVED" if diff > 0 else "DECLINED" if diff < 0 else "NO CHANGE"
            
            print(f"{trend:10} {name:20} | Original: {orig:7.2f}{unit} -> Optimized: {opt:7.2f}{unit} | {arrow} {diff:+.2f}{unit} ({diff_pct:+.1f}%)")
    
    # Save results to CSV for further analysis
    if results_original and results_optimized:
        import json
        with open('backtest_results.json', 'w') as f:
            json.dump({
                'original': results_original,
                'optimized': results_optimized,
                'timestamp': datetime.now().isoformat(),
                'pair': pair_symbol,
                'days': days,
                'timeframe': timeframe
            }, f, default=str, indent=2)
        print(f"\n[SUCCESS] Results saved to backtest_results.json")

if __name__ == '__main__':
    # Test with SOL/USDT (since we have bots for SOL)
    compare_strategies(pair_symbol='SOL/USDT', timeframe='1h', days=60)