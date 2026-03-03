import os
import django
import pandas as pd
import numpy as np
from decimal import Decimal

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')
django.setup()

from dashboard.backtester import DayTradingStrategy
from dashboard.bot_manager import BotManager
from dashboard.models import LiveBot, TradingPair

def simulate_bearish_market():
    print("\n--- Simulando Mercado Bajista (Precio < EMA 200) ---")
    
    # Crear datos: caída constante bajo una EMA 200 de 100
    prices = np.linspace(100, 80, 250)
    df = pd.DataFrame({
        'open': prices,
        'high': prices + 0.5,
        'low': prices - 0.5,
        'close': prices,
        'volume': np.random.randint(100, 1000, 250)
    })
    
    strategy = DayTradingStrategy()
    df_signals = strategy.generate_signals(df)
    
    buys = df_signals[df_signals['signal'] == 'BUY']
    print(f"Señales de BUY encontradas en caída: {len(buys)}")
    if len(buys) == 0:
        print("EXITO: El filtro EMA 200 previno entradas en tendencia bajista.")
    else:
        print("FALLO: Se encontraron entradas en tendencia bajista.")

def simulate_trend_reversal():
    print("\n--- Simulando Recuperación (Cruce EMA 200 + MACD) ---")
    
    # Crear datos: caída larga y luego subida EXPLOSIVA
    # 200 velas de caída lenta de 100 a 80
    # 100 velas de subida rápida de 80 a 150
    prices = list(np.linspace(100, 80, 200)) + list(np.linspace(80, 150, 100))
    df = pd.DataFrame({
        'open': prices,
        'high': np.array(prices) + 2,
        'low': np.array(prices) - 2,
        'close': prices,
        'volume': np.linspace(100, 2000, 300) # Volumen creciente en la subida
    })
    
    strategy = DayTradingStrategy(parameters={'rsi_buy': 50}) # Bajamos un poco el umbral para el test
    df_signals = strategy.generate_signals(df)
    
    # Debug: ver últimas filas de la subida
    recovery_start = 200
    print(df_signals[['close', 'ema200', 'macd', 'signal_macd', 'rsi', 'signal']].iloc[recovery_start+50:recovery_start+70])
    
    buys = df_signals[df_signals['signal'] == 'BUY']
    print(f"Señales de BUY encontradas en recuperación: {len(buys)}")
    if len(buys) > 0:
        print(f"EXITO: Se detectaron entradas válidas tras el cambio de tendencia.")
        last_buy = buys.iloc[-1]
        print(f"Ultimo SL: {last_buy['stop_loss']}, TP: {last_buy['take_profit']}")
    else:
        print("FALLO: No se detectaron entradas en la recuperación. Ver indicadores arriba.")

if __name__ == "__main__":
    simulate_bearish_market()
    simulate_trend_reversal()
