import pandas as pd
import numpy as np
from .indicadores import adx, bollinger_bands

def calculate_range_score(df, period=14):
    """
    Calcula una puntuación de 0 a 100 indicando qué tan 'lateral' es un mercado.
    100 = Rango perfecto, 0 = Tendencia muy fuerte.
    """
    if df is None or len(df) < period * 2:
        return 0, {}

    # 1. ADX (Fuerza de Tendencia)
    # Por debajo de 20-25 se considera sin tendencia (rango)
    adx_series = adx(df, period)
    current_adx = adx_series.iloc[-1]
    
    # Puntuación ADX: Mayor puntaje si ADX es bajo
    # Si ADX < 20 -> 40 pts, lineal hasta 40 -> 0 pts
    adx_score = max(0, min(40, (40 - current_adx) * 2))

    # 2. Bollinger Bandwidth (Volatilidad Relativa)
    # Buscamos 'Squeezes' o bandas estrechas
    df_bb = bollinger_bands(df.copy(), window=20, num_std=2, generate_signals=False)
    current_bw = df_bb['bb_bandwidth'].iloc[-1]
    avg_bw = df_bb['bb_bandwidth'].rolling(window=100).mean().iloc[-1]
    
    # Puntuación Volatilidad: Comparar ancho actual vs histórico
    # Si current_bw < avg_bw, es señal de consolidación
    vol_ratio = current_bw / avg_bw if avg_bw > 0 else 1
    vol_score = max(0, min(30, (1.5 - vol_ratio) * 20))

    # 3. Rango de Precio (Min-Max en periodo reciente)
    recent_period = min(24, len(df)) # Últimas 24 velas
    recent_df = df.tail(recent_period)
    price_min = recent_df['low'].min()
    price_max = recent_df['high'].max()
    price_mean = recent_df['close'].mean()
    
    variation_pct = (price_max - price_min) / price_mean * 100
    # Premiar variaciones entre 1% y 5% (ideal para grids)
    # Muy baja (<1%) = poco profit, Muy alta (>10%) = breakout probable
    if 1 <= variation_pct <= 5:
        price_score = 30
    elif variation_pct < 1:
        price_score = 15
    else:
        price_score = max(0, 30 - (variation_pct - 5) * 3)

    total_score = adx_score + vol_score + price_score
    
    # Valores de referencia para el Grid
    # Sugerimos un margen de seguridad del 1% sobre los extremos recientes
    suggested_lower = round(price_min * 0.995, 4) if price_min < 10 else round(price_min * 0.995, 2)
    suggested_upper = round(price_max * 1.005, 4) if price_max < 10 else round(price_max * 1.005, 2)
    # El escape (stop loss) suele ser un 2-3% fuera del rango
    suggested_stop_loss = round(suggested_lower * 0.98, 2) if price_min > 10 else round(suggested_lower * 0.98, 4)

    details = {
        'adx': round(current_adx, 2),
        'bandwidth': round(current_bw, 4),
        'variation_pct': round(variation_pct, 2),
        'adx_score': round(adx_score, 1),
        'vol_score': round(vol_score, 1),
        'price_score': round(price_score, 1),
        'suggested_lower': suggested_lower,
        'suggested_upper': suggested_upper,
        'suggested_stop_loss': suggested_stop_loss
    }

    return round(total_score, 1), details
