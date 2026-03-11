import pandas as pd
import numpy as np
import sys
import os

# Añadir el path del proyecto para importar las utilidades
project_root = r'C:\Users\Javier\Desktop\programacion\djangoDashPub\criptodash'
sys.path.append(project_root)

# Configurar Django para poder importar modelos e indicadores
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')
import django
django.setup()

from dashboard.backtester import DayTradingStrategy

def generate_mock_data(n=300):
    """Genera datos simulados con una tendencia bajista y luego un giro alcista explosivo."""
    dates = pd.date_range(start='2023-01-01', periods=n, freq='15T')
    
    # Fase 1: Tendencia bajista larga (para que la EMA 200 esté arriba)
    prices_downtrend = 200 - np.cumsum(np.random.normal(0.2, 0.1, 150))
    
    # Fase 2: Giro alcista violento (breakout)
    prices_uptrend = prices_downtrend[-1] + np.cumsum(np.random.normal(1.5, 0.5, 150))
    
    prices = np.concatenate([prices_downtrend, prices_uptrend])
    
    df = pd.DataFrame({
        'timestamp': dates,
        'open': prices * (1 - 0.001),
        'high': prices * (1 + 0.002),
        'low': prices * (1 - 0.002),
        'close': prices,
        'volume': np.random.randint(100, 1000, 300)
    })
    return df

def test_strategy():
    print("--- INICIANDO TEST DE ESTRATEGIA OPTIMIZADA ---")
    df = generate_mock_data(300)
    
    # Probar modo Balanceado (Default)
    strategy = DayTradingStrategy(parameters={'strategy_mode': 'balanced', 'allow_late_entry': True})
    df_results = strategy.generate_signals(df)
    
    signals = df_results[df_results['signal'] != 'HOLD']
    if not signals.empty:
        print(f"\nSeñales encontradas (Balanceado + Late Entry): {len(signals)}")
        print(signals[['signal', 'strength', 'close', 'ema200', 'rsi', 'adx']].tail(10))
    else:
        print("\nNo se encontraron señales en modo Balanceado.")

    # Probar modo Agresivo sin Late Entry (requiere cruce exacto)
    print("\n--- TEST MODO AGRESIVO (Cruces exactos) ---")
    strategy_agg = DayTradingStrategy(parameters={'strategy_mode': 'aggressive', 'allow_late_entry': False})
    df_agg = strategy_agg.generate_signals(df)
    signals_agg = df_agg[df_agg['signal'] != 'HOLD']
    print(f"Señales encontradas (Agresivo): {len(signals_agg)}")
    if not signals_agg.empty:
        print(signals_agg[['signal', 'strength', 'close']].head(10))

if __name__ == "__main__":
    test_strategy()
