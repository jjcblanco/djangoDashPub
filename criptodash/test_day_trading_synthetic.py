import os
import django
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')
django.setup()

from dashboard.backtester import Backtester, DayTradingStrategy
from dashboard.indicadores import calculate_rsi

def test_day_trading_synthetic():
    print("Iniciando Verificación con Datos Sintéticos...")
    
    # 1. Crear 300 barras de datos sintéticos
    # Queremos una tendencia alcista clara después de la barra 210
    dates = [datetime.now() - timedelta(minutes=15*i) for i in range(300)]
    dates.reverse()
    
    close_prices = []
    base_price = 100.0
    for i in range(300):
        if i < 200:
            # Lateral / Leve caída
            base_price -= 0.01
        elif i < 250:
            # Subida fuerte (Crossover EMA)
            base_price += 0.5
        else:
            # Mantenimiento
            base_price += 0.05
        close_prices.append(base_price + np.random.normal(0, 0.1))
        
    df = pd.DataFrame({
        'timestamp': dates,
        'open': close_prices,
        'high': [p + 0.2 for p in close_prices],
        'low': [p - 0.2 for p in close_prices],
        'close': close_prices,
        'volume': [1000] * 300
    })
    
    print(f"Datos sintéticos generados: {len(df)} filas.")
    
    # 2. Probar la estrategia
    strategy = DayTradingStrategy()
    print(f"Generando señales con {strategy.name}...")
    df_signals = strategy.generate_signals(df)
    
    buys = df_signals[df_signals['signal'] == 'BUY']
    sells = df_signals[df_signals['signal'] == 'SELL']
    
    print(f"Señales generadas: BUY={len(buys)}, SELL={len(sells)}")
    
    if len(buys) > 0:
        print("\n✅ SEÑAL DE COMPRA ENCONTRADA:")
        print(buys.iloc[0][['timestamp', 'close', 'ema9', 'ema21', 'ema50', 'ema200', 'rsi']])
        
        # 3. Ejecutar backtest simulado
        backtester = Backtester(initial_balance=1000)
        print("\nEjecutando backtest simulado...")
        results = backtester.simulate_trading(df_signals)
        
        print(f"Retorno Total: {results['total_return']:.2f}%")
        print(f"Trades totales: {results['total_trades']}")
        
        if results['total_trades'] > 0:
            print("\n✅ TEST EXITOSO: La estrategia generó señales y ejecutó trades.")
        else:
            print("\n❌ TEST FALLIDO: Se generaron señales pero no se ejecutaron trades.")
    else:
        print("\n❌ TEST FALLIDO: No se generaron señales de COMPRA.")
        # Debugging: mostrar estado de EMAs al final
        print("\nEstado final de indicadores:")
        print(df_signals.tail(1)[['ema9', 'ema21', 'ema50', 'ema200', 'rsi']])

if __name__ == "__main__":
    test_day_trading_synthetic()
