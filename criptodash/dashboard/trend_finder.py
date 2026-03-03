import pandas as pd
import numpy as np
from .indicadores import adx

def calculate_trend_score(df, period=14):
    """
    Calcula una puntuación de tendencia (alcista o bajista).
    Retorna (score, trend_type, details)
    score: 0 a 100 (fuerza de la tendencia)
    trend_type: 'BULLISH', 'BEARISH' o 'NEUTRAL'
    """
    if df is None or len(df) < 200:
        return 0, 'NEUTRAL', {}

    # 1. EMAs de referencia
    df['ema9'] = df['close'].ewm(span=9, adjust=False).mean()
    df['ema21'] = df['close'].ewm(span=21, adjust=False).mean()
    df['ema50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['ema200'] = df['close'].ewm(span=200, adjust=False).mean()
    
    current_price = float(df['close'].iloc[-1])
    e9 = float(df['ema9'].iloc[-1])
    e21 = float(df['ema21'].iloc[-1])
    e50 = float(df['ema50'].iloc[-1])
    e200 = float(df['ema200'].iloc[-1])
    
    # 2. ADX (Fuerza de Tendencia)
    adx_series = adx(df, period)
    current_adx = float(adx_series.iloc[-1])
    
    # 3. Lógica de Dirección
    if current_price > e200:
        trend_type = 'BULLISH'
        # Alineación: e9 > e21 > e50 > e200
        alignment_score = 0
        if e9 > e21: alignment_score += 10
        if e21 > e50: alignment_score += 10
        if e50 > e200: alignment_score += 20
        
        # Distancia del precio a la EMA 200 (queremos que no esté extremadamente lejos para evitar reversiones)
        dist_ema = (current_price - e200) / e200 * 100
        dist_score = max(0, min(20, 20 - abs(dist_ema - 5))) # Idealmente un 5% sobre la EMA
    else:
        trend_type = 'BEARISH'
        # Alineación: e9 < e21 < e50 < e200
        alignment_score = 0
        if e9 < e21: alignment_score += 10
        if e21 < e50: alignment_score += 10
        if e50 < e200: alignment_score += 20
        
        dist_ema = (e200 - current_price) / e200 * 100
        dist_score = max(0, min(20, 20 - abs(dist_ema - 5)))

    # Puntuación ADX (Fuerza)
    adx_score = max(0, min(40, (current_adx - 15) * 2)) # Empieza a puntuar desde ADX 15

    total_score = alignment_score + dist_score + adx_score
    
    # Si ADX es muy bajo (<15), forzar tendencia neutral
    if current_adx < 15:
        trend_type = 'NEUTRAL'

    details = {
        'adx': round(current_adx, 2),
        'e50': round(e50, 2),
        'e200': round(e200, 2),
        'dist_ema': round(dist_ema, 2),
        'alignment_score': alignment_score,
        'dist_score': dist_score,
        'adx_score': adx_score
    }
    
    return round(total_score, 1), trend_type, details
