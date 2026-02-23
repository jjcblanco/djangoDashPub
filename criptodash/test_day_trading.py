import os
import django
import pandas as pd
from datetime import datetime, timedelta
from django.utils import timezone

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')
django.setup()

from dashboard.models import TradingPair, OHLCVData
from dashboard.data_service import DataManager
from dashboard.backtester import Backtester, DayTradingStrategy

def test_day_trading_strategy():
    pair_symbol = 'BNB/USDT'
    timeframe = '15m'
    
    # Obtener el par
    try:
        pair = TradingPair.objects.get(symbol=pair_symbol)
    except TradingPair.DoesNotExist:
        print(f"Error: Par {pair_symbol} no encontrado.")
        return

    # Obtener datos OHLCV recientes
    end_date = timezone.now()
    start_date = end_date - timedelta(days=60) # 60 días para tener EMAs y capturar más ciclos
    
    print(f"Obteniendo datos para {pair_symbol} {timeframe}...")
    df = DataManager.get_or_fetch(pair_symbol, timeframe, start=start_date, end=end_date, limit=5000)
    
    if df.empty:
        print("No se pudieron obtener datos.")
        return
        
    # Asegurar que las columnas tengan el tipo correcto
    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = df[col].astype(float)
        
    print(f"Datos cargados: {len(df)} filas.")
    
    # Probar la estrategia
    strategy = DayTradingStrategy()
    print(f"Generando señales con {strategy.name}...")
    df_signals = strategy.generate_signals(df)
    
    buys = df_signals[df_signals['signal'] == 'BUY']
    sells = df_signals[df_signals['signal'] == 'SELL']
    
    print(f"Señales generadas: BUY={len(buys)}, SELL={len(sells)}")
    
    if len(buys) > 0:
        print("\nEjemplo de señal de COMPRA:")
        print(buys.iloc[0][['timestamp', 'close', 'ema9', 'ema21', 'ema50', 'ema200', 'rsi']])
        
    # Ejecutar backtest simulado
    backtester = Backtester(initial_balance=1000)
    print("\nEjecutando backtest simulado...")
    results = backtester.simulate_trading(df_signals)
    
    print(f"Retorno Total: {results['total_return']:.2f}%")
    print(f"Trades totales: {results['total_trades']}")

if __name__ == "__main__":
    test_day_trading_strategy()
