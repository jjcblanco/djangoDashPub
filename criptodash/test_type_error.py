
import pandas as pd
import numpy as np
import os
import sys

# Agregar el directorio del proyecto al path
sys.path.append(r'c:\Users\Javier\Desktop\programacion\djangoDashPub\criptodash')

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')
import django
django.setup()

from dashboard.backtester import DayTradingStrategy

def test_strategy():
    # Parámetros como estarían en la DB (Strings)
    db_params = {
        'min_strength': '3',
        'min_adx': '20',
        'timeframe': '1h',
        'use_candles': True,
        'ema_fast': '9',
        'ema_med': '21',
        'ema_slow': '50',
        'ema_trend': '200',
        'rsi_buy': '55',
        'rsi_sell': '45',
        'atr_sl': '3.0',
        'atr_tp': '2.0'
    }

    # Crear DataFrame de prueba
    data = {
        'open': [100]*100,
        'high': [101]*100,
        'low': [99]*100,
        'close': [100]*100,
        'volume': [1000]*100
    }
    df = pd.DataFrame(data)

    print("Instanciando estrategia con parámetros de DB (strings)...")
    try:
        strategy = DayTradingStrategy(parameters=db_params)
        print("Estrategia instanciada correctamente.")
        
        print("Generando señales...")
        df_results = strategy.generate_signals(df)
        print("Señales generadas correctamente.")
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_strategy()
