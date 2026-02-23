import os
import django
import pandas as pd
from datetime import datetime, timedelta
from django.utils import timezone

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')
django.setup()

from dashboard.models import TradingPair, TradeSignal, OHLCVData
from dashboard.backtester import Backtester
from dashboard import ccxttest1

def run_optimization(pair_symbol='BNB/USDT', days=90):
    print(f"Starting Optimization Research for {pair_symbol} (Last {days} days)")
    
    end_date = timezone.now()
    start_date = end_date - timedelta(days=days)
    
    timeframes = ['15m', '1h', '4h']
    adx_thresholds = [0, 20, 25, 30]
    min_strengths = [4.0, 4.5]
    
    atr_sl_mults = [1.5, 2.0, 2.5]
    atr_tp_mults = [2.0, 3.0, 4.0]
    
    results_list = []
    
    backtester = Backtester(initial_balance=10000, commission=0.001)
    
    for tf in timeframes:
        print(f"\n--- Testing Timeframe: {tf} ---")
        
        try:
            date_from_str = start_date.strftime('%Y-%m-%d %H:%M:%S')
            ccxttest1.run_bot(pair=pair_symbol, date_from=date_from_str, timeframe=tf)
        except Exception as e:
            print(f"Error generating signals for {tf}: {e}")
            continue
            
        for adx_min in adx_thresholds:
            for strength in min_strengths:
                for sl_mult in atr_sl_mults:
                    for tp_mult in atr_tp_mults:
                        print(f"Testing: ADX>={adx_min}, Str>={strength}, SL={sl_mult}, TP={tp_mult}")
                        
                        res = backtester.run_backtest_from_signals(
                            pair_symbol=pair_symbol,
                            start_date=start_date,
                            end_date=end_date,
                            timeframe=tf,
                            min_strength=strength,
                            min_adx=adx_min,
                            stop_loss_pct=None, # Use ATR
                            take_profit_pct=None, # Use ATR
                            atr_mult_sl=sl_mult,
                            atr_mult_tp=tp_mult,
                            trailing_stop=True
                        )
                        
                        if 'error' not in res and res['total_trades'] > 0:
                            results_list.append({
                                'TF': tf,
                                'ADX': adx_min,
                                'Str': strength,
                                'SL_M': sl_mult,
                                'TP_M': tp_mult,
                                'Ret %': round(res['total_return'], 2),
                                'Win %': round(res.get('win_rate', 0), 2),
                                'Trades': res['total_trades'],
                                'P.Factor': round(res.get('profit_factor', 0), 2),
                                'MaxDD': round(res.get('max_drawdown', 0), 2)
                            })
                else:
                    error_msg = res.get('error', 'No trades')
                    print(f"  Skipped: {error_msg}")

    # Display results
    if results_list:
        df_results = pd.DataFrame(results_list)
        df_results = df_results.sort_values(by='Ret %', ascending=False)
        
        # Save to CSV for persistent analysis
        df_results.to_csv('optimization_results.csv', index=False)
        
        print("\n" + "="*80)
        print("TOP 10 OPTIMIZATION RESULTS")
        print("="*80)
        print(df_results.head(10).to_string(index=False))
        print("="*80)
        
        best = df_results.iloc[0]
        print(f"\nRecommended Configuration: TF={best['TF']}, ADX >= {best['ADX']}, Strength >= {best['Str']}, SL_Mult={best['SL_M']}, TP_Mult={best['TP_M']}")
        print(f"Results saved to optimization_results.csv")
    else:
        print("\nNo successful backtests completed.")

if __name__ == "__main__":
    # Silence DB logging
    import logging
    logging.getLogger('django.db.backends').setLevel(logging.ERROR)
    
    run_optimization()
