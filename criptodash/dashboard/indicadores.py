
# Libreria para calcular indicadores
# Indicadores 
#           TR
#           ATR
#           MACD
#           RSI
#           Supertrade
#           Bollinger Bands



import pandas as pd
import numpy as np

# True range 
# Esta funcion calcula el true range--> Es el maximo de 3 valores
# 1 La diferencia entre high y Low
# 2 La diferencia entre high y el valor anterior de close
# 3 La diferencia entre low y el valor anterior de close

def tr(data):
    data['previous_close'] = data['close'].shift(1)
    data['high_low'] = abs(data['high'] - data['low'])
    data['high_pc'] = abs(data['high'] - data['previous_close'])
    data['low_pc'] = abs(data['low'] - data['previous_close'])

    tr = data[['high_low', 'high_pc', 'low_pc']].max(axis=1)

    return tr

# Average true Range
# Esta funcion calcula el average true range--> Es el promedio de los true range en el
#  indicado( rolling mean)
# Este indicador sirve para medir volatilidad en el mercado

def atr(data, period):
    data['tr'] = tr(data)
    atr = data['tr'].rolling(period).mean()

    return atr


# Indicador RSI  
# Descripcion: El inidicador RSI es un indicador de momento que mide la magnitud de los cambios de 
#               precio para determinar las condiciones de soibrecomprado y sobrevendido.
# Funcion:
#----Overbought and Oversold Conditions----

# Sobre Comprado: Cuando el RSI pasa los 70, eso indica que el activo esta sobrecomprado y se puede dar un pullback o reversal.
# Sobre Vendido: Cuando el RSI cae mas abajo de 30, indica que el activo  esta sobrevendido y se puede dar un pullback o reversal.

# -----Divergencias---
# Divergencia bullish: Cuando el RSI forma un higher low mientras el precio forma un Lower low
#                       ---Es una señal de compra, indica posible impulso ascedente
# Divergencia bearish: Cuando el RSI forma un lower high mientras el precio forma un higher high
#                       ---Es una senal de venta, indica posible impulso descentente
# RSI Breakout: Cuando el rsi rompe por arriba de un nivel de resistencia o un nivel de soporte 
#                puede ser una señal de que el precio va a tener un cambio significativo
                
# ---Tendencias---
# RSI en tendencia alcista: Cuando el RSI esta en un rango de


### No usar en mercado de tendencia ranging 
# 
#  
def calculate_rsi(df, period=14):
    # Calculate the differences between each consecutive closing price
    delta = df['close'].diff()
    
    # Gain (up) and Loss (down)
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    
    # Calculate the RS (Relative Strength)
    rs = gain / loss
    
    # Calculate the RSI value
    rsi = 100 - (100 / (1 + rs))
    
    # Handle division by zero (loss=0)
    rsi = rsi.fillna(100)
    
    return rsi

# Es una funcion que calcula el indicador de tendencia "Supertrade" combina la deteccion de la tendencia y la volatilidad
# Se usa para detectar cambios de tendencia y colocar stop loss.
# Crea dos bandas alrededor del precio promedio separadas por el atr_muliplier
# tambien actualiza la columna "in_trend" siguiendo las sig reglas
# 1 Si la banda superior es mayor que el precio promedio
# 2 Si la banda inferior es menor que el precio promedio
# 3 Si la banda superior es menor que la banda inferior

def supertrend(df, period=7, atr_multiplier=3):
    hl2 = (df['high'] + df['low']) / 2
    df['atr'] = atr(df, period)
    df['upperband'] = hl2 + (atr_multiplier * df['atr'])
    df['lowerband'] = hl2 - (atr_multiplier * df['atr'])
    df['in_uptrend'] = True

    for current in range(1, len(df.index)):
        previous = current - 1

        if df['close'][current] > df['upperband'][previous]:
            df['in_uptrend'][current] = True
        elif df['close'][current] < df['lowerband'][previous]:
            df['in_uptrend'][current] = False
        else:
            df['in_uptrend'][current] = df['in_uptrend'][previous]

            if df['in_uptrend'][current] and df['lowerband'][current] < df['lowerband'][previous]:
                df['lowerband'][current] = df['lowerband'][previous]

            if not df['in_uptrend'][current] and df['upperband'][current] > df['upperband'][previous]:
                df['upperband'][current] = df['upperband'][previous]
        
    return df

# Funcion que calcula el indicador MACD (moving average convergence divergence) 
# 
# Se usa para identificar tendencias, momentum y potenciales señales de compraventa
# Estrategias:  ---Cruce de linea macd por arriba de linea de señal: Bullish(buy) impulso alcista
#               ---Cruce de linea macd por abajo de linea de señal: Bearish(sell) impulso bajista
#               ---Cruce de linea macd por arriba de linea de CERO: Buy signal
#               ---Cruce de linea macd por abajo de linea de CERO: Sell signal
# Divergencias: -- Bullish Buy es cuando la linea MACD forma un Higher Low  mientras el precio hace un lower low
#                  Eso es un potencial impulso alcisita
#               -- Bearish Sell es cuando la linea MACD forma un Lower High mientras el precio hace un higher high
#
# Analisis de histograma
#               -- Cuando el histograma crece, crece el impulso u lo mismo para cuando decrece

def macd(df, short_period=12, long_period=26, signal_period=9):
    df['ema_short'] = df['close'].ewm(span=short_period, adjust=False).mean()
    df['ema_long'] = df['close'].ewm(span=long_period, adjust=False).mean()
    df['macd'] = df['ema_short'] - df['ema_long']
    df['signal_macd'] = df['macd'].ewm(span=signal_period, adjust=False).mean()
    df['macd_hist'] = df['macd'] - df['signal_macd']
    return df

def ema(df, period=200):
    """Calcula la Media Móvil Exponencial"""
    return df['close'].ewm(span=period, adjust=False).mean()

def obv(df):
    """
    On-Balance Volume (OBV)
    Measure buying and selling pressure as a cumulative indicator.
    """
    return (np.sign(df['close'].diff()) * df['volume']).fillna(0).cumsum()

def vwap(df):
    """
    Volume Weighted Average Price (VWAP)
    """
    v = df['volume']
    p = (df['high'] + df['low'] + df['close']) / 3
    return (p * v).cumsum() / v.cumsum()


def adx(df, period=14):
    """
    Average Directional Index (ADX)
    Mide la fuerza de la tendencia.
    """
    df = df.copy()
    df['tr'] = tr(df)
    
    # +DM y -DM
    df['up_move'] = df['high'] - df['high'].shift(1)
    df['down_move'] = df['low'].shift(1) - df['low']
    
    df['plus_dm'] = np.where((df['up_move'] > df['down_move']) & (df['up_move'] > 0), df['up_move'], 0)
    df['minus_dm'] = np.where((df['down_move'] > df['up_move']) & (df['down_move'] > 0), df['down_move'], 0)
    
    # Wilder's Smoothing
    alpha = 1 / period
    df['tr_smooth'] = df['tr'].ewm(alpha=alpha, adjust=False).mean()
    df['plus_dm_smooth'] = df['plus_dm'].ewm(alpha=alpha, adjust=False).mean()
    df['minus_dm_smooth'] = df['minus_dm'].ewm(alpha=alpha, adjust=False).mean()
    
    # DI+ y DI-
    df['plus_di'] = 100 * (df['plus_dm_smooth'] / df['tr_smooth'])
    df['minus_di'] = 100 * (df['minus_dm_smooth'] / df['tr_smooth'])
    
    # DX y ADX
    df['dx'] = 100 * (abs(df['plus_di'] - df['minus_di']) / (df['plus_di'] + df['minus_di']))
    adx_series = df['dx'].ewm(alpha=alpha, adjust=False).mean()
    
    return adx_series


def volume_ma(df, period=20):
    """
    Calcula la media móvil del volumen para detectar picos.
    """
    return df['volume'].rolling(window=period).mean()

def calculate_sl_tp(df, signal_type, atr_period=14, atr_multiplier_sl=1.5, atr_multiplier_tp=3.0):
    """
    Calcula niveles de Stop Loss y Take Profit basados en ATR
    """
    if 'atr' not in df.columns:
        df['atr'] = atr(df, atr_period)
    
    # Usar el valor actual de ATR para el cálculo
    current_atr = df['atr']
    
    if signal_type == 'buy':
        sl = df['close'] - (current_atr * atr_multiplier_sl)
        tp = df['close'] + (current_atr * atr_multiplier_tp)
    else:  # sell
        sl = df['close'] + (current_atr * atr_multiplier_sl)
        tp = df['close'] - (current_atr * atr_multiplier_tp)
        
    return sl, tp


# ///Calculate the Bollinger Bands with a window size of 20 and standard deviation of 2 ////

# ***bollinger bands*** indican miden volatilidad(velocidad de cambio del precio) 
# El momento en que las bandas se acercan se llama squeeze e indica un periodo de baja volatilidad y 
# se puede ver que apartir de ello va a aumentar la volatilidad y cuado se alejan hay mucha volatilidad
# y se espera que esa volatilidad se reduzca.
# No es un indicador de un cambio en el precio directamente pero pueden indicar cuando una tendencia esta llegando a 
# su fin. 
# En el caso de volumenes puede indicar en el momento un interes menor en un activo cuando los volumenes
# descienden y las bandas de acercan.
# cuando una banda superior empieza a empjar el precio podria haber una reversion pero no es siempre
# asi, hay que comparar con rsi otros ind

# ---Cuando la distancia entre bandas es angosta indica que se esta en zona ranging o zona de baja volatilidad

def bollinger_bands(data, window=20, num_std=2, generate_signals=True):
    """
    Calcula Bollinger Bands mejoradas con múltiples señales
    
    Parameters:
    - data: DataFrame con columnas OHLC
    - window: Período para la media móvil (default 20)
    - num_std: Número de desviaciones estándar (default 2)
    - generate_signals: Si genera señales de compra/venta
    
    Returns:
    - DataFrame con Bollinger Bands y señales
    """
    
    # Calcular componentes básicos
    data['bb_middle'] = data['close'].rolling(window=window).mean()
    data['bb_std'] = data['close'].rolling(window=window).std()
    
    # Bandas superior e inferior
    data['bb_upper'] = data['bb_middle'] + (data['bb_std'] * num_std)
    data['bb_lower'] = data['bb_middle'] - (data['bb_std'] * num_std)
    
    # Bandas adicionales (para más información)
    data['bb_upper_1std'] = data['bb_middle'] + data['bb_std']  # 1 desviación
    data['bb_lower_1std'] = data['bb_middle'] - data['bb_std']  # 1 desviación
    
    # Ancho de las bandas (indicador de volatilidad)
    data['bb_width'] = (data['bb_upper'] - data['bb_lower']) / data['bb_middle']
    
    # Posición del precio relativa a las bandas
    data['bb_position'] = (data['close'] - data['bb_lower']) / (data['bb_upper'] - data['bb_lower'])
    
    # %B indicator
    data['bb_percent_b'] = (data['close'] - data['bb_lower']) / (data['bb_upper'] - data['bb_lower'])
    
    # Bandwidth (ancho normalizado)
    data['bb_bandwidth'] = (data['bb_upper'] - data['bb_lower']) / data['bb_middle']
    
    # Squeeze Indicator (Banda moviéndose en el 20% inferior de su ancho histórico reciente)
    # Indica que el mercado está en calma y se prepara para un movimiento explosivo
    bandwidth_min = data['bb_bandwidth'].rolling(window=100).min()
    bandwidth_max = data['bb_bandwidth'].rolling(window=100).max()
    data['bb_squeezing'] = data['bb_bandwidth'] < (bandwidth_min + (bandwidth_max - bandwidth_min) * 0.2)
    
    # Generar señales si se solicita
    if generate_signals:
        data = generate_bb_signals(data, window)
    
    return data

def generate_bb_signals(data, window):
    """
    Genera señales de compra/venta basadas en Bollinger Bands
    """
    # Inicializar columna de señales si no existe
    if 'signal_buy_sell' not in data.columns:
        data['signal_buy_sell'] = ' '
    
    # Estrategia 1: Rebote en bandas
    data = bb_bounce_strategy(data, window)
    
    # Estrategia 2: Squeeze (compresión)
    data = bb_squeeze_strategy(data)
    
    # Estrategia 3: Breakout con confirmación
    data = bb_breakout_strategy(data, window)
    
    # Estrategia 4: Tendencia con bandas
    data = bb_trend_strategy(data)
    
    return data
def bb_bounce_strategy(data, window):
    """
    Señales cuando el precio rebota en las bandas
    """
    #print(data.loc[:,['timestamp', 'close', 'signal_buy_sell']].head())
    
    for i in range(window, len(data)):
        current_close = data['close'].iloc[i]
        previous_close = data['close'].iloc[i-1]
        bb_upper = data['bb_upper'].iloc[i]
        bb_lower = data['bb_lower'].iloc[i]
        bb_middle = data['bb_middle'].iloc[i]
        
        # SEÑAL DE COMPRA: Rebote en banda inferior
        buy_conditions = [
            # Precio toca o cruza la banda inferior
            current_close <= bb_lower or previous_close <= bb_lower,
            # Y luego se recupera
            current_close > previous_close,
            # Confirmación: precio por encima del mínimo reciente
            current_close > data['low'].iloc[i-3:i].min(),
            # Volumen creciente (si está disponible)
            'volume' in data.columns and data['volume'].iloc[i] > data['volume'].iloc[i-1] if 'volume' in data.columns else True
        ]
        
        # SEÑAL DE VENTA: Rebote en banda superior
        sell_conditions = [
            # Precio toca o cruza la banda superior
            current_close >= bb_upper or previous_close >= bb_upper,
            # Y luego retrocede
            current_close < previous_close,
            # Confirmación: precio por debajo del máximo reciente
            current_close < data['high'].iloc[i-3:i].max(),
            # Volumen creciente (si está disponible)
            'volume' in data.columns and data['volume'].iloc[i] > data['volume'].iloc[i-1] if 'volume' in data.columns else True
        ]
        
        # Asignar señales (priorizar señales fuertes)
        if sum(buy_conditions) >= 3 and data['signal_buy_sell'].iloc[i] == '':
            data.loc[data.index[i], 'signal_buy_sell'] = 'buy'
            data.loc[data.index[i], 'signal_type'] = 'BB_BOUNCE'
        
        elif sum(sell_conditions) >= 3 and data['signal_buy_sell'].iloc[i] == '':
            data.loc[data.index[i], 'signal_buy_sell'] = 'sell'
            data.loc[data.index[i], 'signal_type'] = 'BB_BOUNCE'
    #print(data['signal_buy_sell'])
    return data
def bb_squeeze_strategy(data):
    """
    Señales cuando las bandas se comprimen (baja volatilidad)
    seguido de expansión (posible breakout)
    """
    # Umbral para considerar squeeze (bandas muy estrechas)
    squeeze_threshold = data['bb_bandwidth'].quantile(0.1)  # 10% más estrecho
    
    for i in range(20, len(data)):
        # Condición de SQUEEZE: bandas muy estrechas
        is_squeeze = data['bb_bandwidth'].iloc[i] < squeeze_threshold
        
        # Buscar expansión después del squeeze
        if is_squeeze:
            # Mirar hacia adelante para detectar expansión
            for j in range(i+1, min(i+10, len(data))):
                expansion = data['bb_bandwidth'].iloc[j] > squeeze_threshold * 2
                
                if expansion:
                    direction = 'buy' if data['close'].iloc[j] > data['bb_middle'].iloc[j] else 'sell'
                    
                    if data['signal_buy_sell'].iloc[j] == '':
                        data.loc[data.index[j], 'signal_buy_sell'] = direction
                        data.loc[data.index[j], 'signal_type'] = 'BB_SQUEEZE'
                    break
    
    return data

def bb_breakout_strategy(data, window):
    """
    Señales de breakout con confirmación
    """
    for i in range(window, len(data)):
        current_close = data['close'].iloc[i]
        previous_close = data['close'].iloc[i-1]
        bb_upper = data['bb_upper'].iloc[i]
        bb_lower = data['bb_lower'].iloc[i]
        
        # BREAKOUT ALCISTA: Rompe banda superior con fuerza
        bullish_breakout = [
            current_close > bb_upper,
            current_close > previous_close,
            data['high'].iloc[i] > data['high'].iloc[i-1],
            data['close'].iloc[i] > data['open'].iloc[i],  # Vela alcista
            data['bb_bandwidth'].iloc[i] > data['bb_bandwidth'].iloc[i-1]  # Expansión
        ]
        
        # BREAKOUT BAJISTA: Rompe banda inferior con fuerza
        bearish_breakout = [
            current_close < bb_lower,
            current_close < previous_close,
            data['low'].iloc[i] < data['low'].iloc[i-1],
            data['close'].iloc[i] < data['open'].iloc[i],  # Vela bajista
            data['bb_bandwidth'].iloc[i] > data['bb_bandwidth'].iloc[i-1]  # Expansión
        ]
        
        if sum(bullish_breakout) >= 4 and data['signal_buy_sell'].iloc[i] == '':
            data.loc[data.index[i], 'signal_buy_sell'] = 'buy'
            data.loc[data.index[i], 'signal_type'] = 'BB_BREAKOUT'
        
        elif sum(bearish_breakout) >= 4 and data['signal_buy_sell'].iloc[i] == '':
            data.loc[data.index[i], 'signal_buy_sell'] = 'sell'
            data.loc[data.index[i], 'signal_type'] = 'BB_BREAKOUT'
    
    return data

def bb_trend_strategy(data):
    """
    Señales basadas en la tendencia y posición en las bandas
    """
    for i in range(20, len(data)):
        # Tendencia alcista: precio sobre la media móvil
        uptrend = data['close'].iloc[i] > data['bb_middle'].iloc[i]
        
        # Tendencia bajista: precio bajo la media móvil
        downtrend = data['close'].iloc[i] < data['bb_middle'].iloc[i]
        
        # Sobrecompra: precio cerca de banda superior
        overbought = data['bb_percent_b'].iloc[i] > 0.8
        
        # Sobrevendido: precio cerca de banda inferior
        oversold = data['bb_percent_b'].iloc[i] < 0.2
        
        # SEÑAL: Compra en tendencia alcista con retroceso a sobrevendido
        if uptrend and oversold and data['signal_buy_sell'].iloc[i] == '':
            # Confirmación: precio comienza a recuperarse
            if data['close'].iloc[i] > data['close'].iloc[i-1]:
                data.loc[data.index[i], 'signal_buy_sell'] = 'buy'
                data.loc[data.index[i], 'signal_type'] = 'BB_TREND'
        
        # SEÑAL: Venta en tendencia bajista con rally a sobrecomprado
        elif downtrend and overbought and data['signal_buy_sell'].iloc[i] == '':
            # Confirmación: precio comienza a caer
            if data['close'].iloc[i] < data['close'].iloc[i-1]:
                data.loc[data.index[i], 'signal_buy_sell'] = 'sell'
                data.loc[data.index[i], 'signal_type'] = 'BB_TREND'
    
    return data


# Ichimoku Cloud
# https://www.investopedia.com/terms/i/ichimoku-cloud.asp
# Tenkan---conversion
# Kijun---base
# chikou--span con retraso
 

def ichimoku_cloud(data, tenkan=9, kijun=26, senkou=52):
    """
    Calcula Ichimoku Cloud y genera señales de compra/venta
    """
    # Calcular componentes Ichimoku (tu código actual mejorado)
    data['tenkan'] = (data['high'].rolling(tenkan).max() + data['low'].rolling(tenkan).min()) / 2
    data['kijun'] = (data['high'].rolling(kijun).max() + data['low'].rolling(kijun).min()) / 2
    data['senkou_a'] = ((data['tenkan'] + data['kijun']) / 2).shift(kijun)
    data['senkou_b'] = ((data['high'].rolling(senkou).max() + data['low'].rolling(senkou).min()) / 2).shift(kijun)
    data['chikou'] = data['close'].shift(-kijun)
    
    # Calcular senkou_c (tu lógica actual)
    data['senkou_c'] = np.nan
    for current in range(1, len(data.index)):
        if data['senkou_a'][current] < data['senkou_b'][current]:
            data['senkou_c'][current] = data['senkou_a'][current]
        elif data['senkou_a'][current] > data['senkou_b'][current]:
            data['senkou_c'][current] = data['senkou_b'][current]
        elif data['senkou_a'][current] == data['senkou_b'][current]:
            data['senkou_c'][current] = data['senkou_b'][current]
    
    # ✅ AGREGAR ESTA NUEVA FUNCIONALIDAD:
    # Generar señales de compra/venta
    print("Generando señales de ichimoku compra/venta...")
    data = generar_señales_ichimoku(data, kijun)
    
    return data

def generar_señales_ichimoku(data, kijun=26):
    """
    Genera señales de compra/venta basadas en Ichimoku
    """
    # Inicializar columna de señales si no existe
    if 'signal_buy_sell' not in data.columns:
        data['signal_buy_sell'] = ' '
    if 'signal_strenght' not in data.columns:
        data['signal_strenght'] = 0
    else:
        # Asegurar que los valores existentes sean numéricos
        data['signal_strenght'] = pd.to_numeric(data['signal_strenght'], errors='coerce').fillna(0)

    # Generar señales para cada punto a partir del período kijun
    for i in range(kijun, len(data)):
        # Condiciones para SEÑAL DE COMPRA
        current_strength = data['signal_strenght'].iloc[i] if i < len(data) else 0
        if not isinstance(current_strength, (int, float)):
            current_strength = 0
        condiciones_compra = [
            # 1. TK Cross Alcista (Tenkan cruza Kijun hacia arriba)
            (data['tenkan'].iloc[i] > data['kijun'].iloc[i]) and 
            (data['tenkan'].iloc[i-1] <= data['kijun'].iloc[i-1]),
            
            # 2. Precio por encima de la nube
            (data['close'].iloc[i] > data['senkou_a'].iloc[i]) and 
            (data['close'].iloc[i] > data['senkou_b'].iloc[i]),
            
            # 3. Nube alcista (Senkou A > Senkou B)
            data['senkou_a'].iloc[i] > data['senkou_b'].iloc[i],
            
            # 4. Confirmación Chikou Span (opcional)
            (i >= kijun*2) and (data['chikou'].iloc[i-kijun] > data['close'].iloc[i-kijun])
        ]
        
        # Condiciones para SEÑAL DE VENTA
        condiciones_venta = [
            # 1. TK Cross Bajista (Tenkan cruza Kijun hacia abajo)
            (data['tenkan'].iloc[i] < data['kijun'].iloc[i]) and 
            (data['tenkan'].iloc[i-1] >= data['kijun'].iloc[i-1]),
            
            # 2. Precio por debajo de la nube
            (data['close'].iloc[i] < data['senkou_a'].iloc[i]) and 
            (data['close'].iloc[i] < data['senkou_b'].iloc[i]),
            
            # 3. Nube bajista (Senkou A < Senkou B)
            data['senkou_a'].iloc[i] < data['senkou_b'].iloc[i],
            
            # 4. Confirmación Chikou Span (opcional)
            (i >= kijun*2) and (data['chikou'].iloc[i-kijun] < data['close'].iloc[i-kijun])
        ]
        
        # Contar condiciones cumplidas
        compra_count = sum(condiciones_compra)
        venta_count = sum(condiciones_venta)
        current_strength = data['signal_strenght'].iloc[i]
        # Asignar señales (mínimo 2 condiciones para señal)
        if compra_count >= 2:
            data.at[data.index[i], 'signal_buy_sell'] = 'buy'
            data.at[data.index[i], 'signal_strenght'] = current_strength + compra_count
        
        elif venta_count >= 2:
            data.at[data.index[i], 'signal_buy_sell'] = 'sell'
            data.at[data.index[i], 'signal_strenght'] = current_strength + venta_count
        # Si no se cumple ninguna condición, se mantiene vacío
    print("señales de compra/venta generadas")
    return data

def enhanced_bollinger_bands(data, window=20, num_std=2, strategy='all'):
    """
    Función completa de Bollinger Bands mejorada
    
    Parameters:
    - strategy: 'bounce', 'squeeze', 'breakout', 'trend', 'all'
    """
    
    # Calcular bandas básicas
    data = bollinger_bands(data, window, num_std, generate_signals=True)
    print("bandas básicas calculadas")
    # Aplicar estrategias seleccionadas
    if strategy in ['bounce', 'all']:
        data = bb_bounce_strategy(data, window)
        print("bounce aplicadas")
    if strategy in ['squeeze', 'all']:
        data = bb_squeeze_strategy(data)
    print("squeeze y bounce aplicadas")
    if strategy in ['breakout', 'all']:
        data = bb_breakout_strategy(data, window)
    print("breakout aplicada")
    if strategy in ['trend', 'all']:
        data = bb_trend_strategy(data)
    print("trend aplicada")
    print("estrategias aplicadas")
    # Limpiar señales duplicadas (priorizar la primera señal)
    data = clean_duplicate_signals(data)
    print("señales duplicadas limpiadas")
    return data

def clean_duplicate_signals(data):
    """
    Limpia señales duplicadas consecutivas
    """
    last_signal = ''
    for i in range(len(data)):
        current_signal = data['signal_buy_sell'].iloc[i]
        if current_signal == last_signal and current_signal != '':
            data.loc[data.index[i], 'signal_buy_sell'] = ''
        else:
            last_signal = current_signal
    
    return data

# Donchian Channels
# window 20
def donchian_channels(data,window):
    data['upper_channel'] = data['high'].rolling(window=window).max()
    data['lower_channel'] = data['low'].rolling(window=window).min()
    return data


def generate_rsi_signals(df, rsi_period=14, overbought=70, oversold=30):
    """
    Genera señales de compra/venta basadas en el RSI
    
    Parameters:
    - df: DataFrame con datos OHLC
    - rsi_period: Período para calcular RSI (default 14)
    - overbought: Nivel de sobrecompra (default 70)
    - oversold: Nivel de sobreventa (default 30)
    
    Returns:
    - DataFrame con señales RSI agregadas
    """
    
    # Calcular RSI si no existe
    if 'rsi' not in df.columns:
        df['rsi'] = calculate_rsi(df, rsi_period)
    
    # Inicializar columnas si no existen
    if 'signal_buy_sell' not in df.columns:
        df['signal_buy_sell'] = ''
    if 'signal_type' not in df.columns:
        df['signal_type'] = ''
    if 'signal_strenght' not in df.columns:
        df['signal_strenght'] = 0
    
    # Generar señales para cada punto
    for i in range(1, len(df)):
        current_strength = df['signal_strenght'].iloc[i]
        current_rsi = df['rsi'].iloc[i]
        previous_rsi = df['rsi'].iloc[i-1]
        
        # SEÑAL DE COMPRA: RSI sale de zona de sobreventa
        buy_conditions = [
            # RSI estaba en zona de sobreventa y ahora sale
            previous_rsi <= oversold and current_rsi > oversold,
            # Confirmación: RSI en tendencia alcista
            current_rsi > previous_rsi,
            # El precio confirma (opcional)
            df['close'].iloc[i] > df['close'].iloc[i-1]
        ]
        
        # SEÑAL DE VENTA: RSI sale de zona de sobrecompra
        sell_conditions = [
            # RSI estaba en zona de sobrecompra y ahora sale
            previous_rsi >= overbought and current_rsi < overbought,
            # Confirmación: RSI en tendencia bajista
            current_rsi < previous_rsi,
            # El precio confirma (opcional)
            df['close'].iloc[i] < df['close'].iloc[i-1]
        ]
        
        # SEÑAL FUERTE: Divergencia alcista
        bullish_divergence = detect_bullish_divergence(df, i, rsi_period)
        
        # SEÑAL FUERTE: Divergencia bajista
        bearish_divergence = detect_bearish_divergence(df, i, rsi_period)
        
        # Asignar señales (priorizar divergencias)
        if bullish_divergence and df['signal_buy_sell'].iloc[i] == '':
            df.loc[df.index[i], 'signal_buy_sell'] = 'buy'
            df.loc[df.index[i], 'signal_type'] = 'RSI_DIVERGENCE'
            df.loc[df.index[i], 'signal_strenght'] = current_strength + 2
        
        elif bearish_divergence and df['signal_buy_sell'].iloc[i] == '':
            df.loc[df.index[i], 'signal_buy_sell'] = 'sell'
            df.loc[df.index[i], 'signal_type'] = 'RSI_DIVERGENCE'
            df.loc[df.index[i], 'signal_strenght'] = current_strength + 2
            
        elif sum(buy_conditions) >= 2 and df['signal_buy_sell'].iloc[i] == '':
            df.loc[df.index[i], 'signal_buy_sell'] = 'buy'
            df.loc[df.index[i], 'signal_type'] = 'RSI_OVERSOLD'
            df.loc[df.index[i], 'signal_strenght'] = current_strength + 1
            
        elif sum(sell_conditions) >= 2 and df['signal_buy_sell'].iloc[i] == '':
            df.loc[df.index[i], 'signal_buy_sell'] = 'sell'
            df.loc[df.index[i], 'signal_type'] = 'RSI_OVERBOUGHT'
            df.loc[df.index[i], 'signal_strenght'] = current_strength + 1
    
    return df

def detect_bullish_divergence(df, current_index, lookback_period=14):
    """
    Detecta divergencia alcista: Precio hace lower low, RSI hace higher low
    """
    if current_index < lookback_period * 2:
        return False
    
    # Buscar mínimo reciente en precio
    price_lookback = df['close'].iloc[current_index-lookback_period:current_index]
    if len(price_lookback) < 5:
        return False
    
    current_low = df['low'].iloc[current_index]
    recent_lows = df['low'].iloc[current_index-5:current_index]
    
    # Buscar mínimo reciente en RSI
    rsi_lookback = df['rsi'].iloc[current_index-lookback_period:current_index]
    current_rsi = df['rsi'].iloc[current_index]
    recent_rsi = df['rsi'].iloc[current_index-5:current_index]
    
    # Condiciones para divergencia alcista
    is_price_lower_low = current_low == recent_lows.min()
    is_rsi_higher_low = current_rsi > recent_rsi.min()
    
    return is_price_lower_low and is_rsi_higher_low

def detect_bearish_divergence(df, current_index, lookback_period=14):
    """
    Detecta divergencia bajista: Precio hace higher high, RSI hace lower high
    """
    if current_index < lookback_period * 2:
        return False
    
    # Buscar máximo reciente en precio
    price_lookback = df['high'].iloc[current_index-lookback_period:current_index]
    if len(price_lookback) < 5:
        return False
    
    current_high = df['high'].iloc[current_index]
    recent_highs = df['high'].iloc[current_index-5:current_index]
    
    # Buscar máximo reciente en RSI
    rsi_lookback = df['rsi'].iloc[current_index-lookback_period:current_index]
    current_rsi = df['rsi'].iloc[current_index]
    recent_rsi = df['rsi'].iloc[current_index-5:current_index]
    
    # Condiciones para divergencia bajista
    is_price_higher_high = current_high == recent_highs.max()
    is_rsi_lower_high = current_rsi < recent_rsi.max()
    
    return is_price_higher_high and is_rsi_lower_high

# Función mejorada de RSI que incluye señales
def calculate_rsi_with_signals(df, period=14, overbought=70, oversold=30):
    """
    Calcula RSI y genera señales en un solo paso
    """
    df = calculate_rsi(df, period)
    df = generate_rsi_signals(df, period, overbought, oversold)
    return df

# --- Candlestick Patterns ---

def detect_candlestick_patterns(df):
    """
    Detects basic candlestick patterns: Hammer, Shooting Star, Engulfing.
    Returns the dataframe with pattern flags.
    """
    # 1. Body and Wicks calculation
    df['body_size'] = (df['close'] - df['open']).abs()
    df['candle_range'] = df['high'] - df['low']
    df['upper_wick'] = df['high'] - df[['open', 'close']].max(axis=1)
    df['lower_wick'] = df[['open', 'close']].min(axis=1) - df['low']
    
    # Avoid division by zero
    range_safe = df['candle_range'].replace(0, 0.000001)
    
    # 2. Pattern: Hammer (Martillo)
    # Green/Red candle with small body, long lower wick (>= 2x body), little to no upper wick
    df['is_hammer'] = (
        (df['lower_wick'] >= 2 * df['body_size']) & 
        (df['upper_wick'] <= 0.1 * df['candle_range']) &
        (df['body_size'] > 0)
    )
    
    # 3. Pattern: Shooting Star (Estrella Fugaz)
    # Green/Red candle with small body, long upper wick (>= 2x body), little to no lower wick
    df['is_shooting_star'] = (
        (df['upper_wick'] >= 2 * df['body_size']) & 
        (df['lower_wick'] <= 0.1 * df['candle_range']) &
        (df['body_size'] > 0)
    )
    
    # 4. Pattern: Bullish Engulfing (Envolvente Alcista)
    # Previous: Red, Current: Green, Current body covers previous body
    df['is_bullish_engulfing'] = (
        (df['close'].shift(1) < df['open'].shift(1)) & # Prev red
        (df['close'] > df['open']) &                  # Curr green
        (df['close'] > df['open'].shift(1)) &         # Green close higher than red open
        (df['open'] < df['close'].shift(1))           # Green open lower than red close
    )
    
    # 5. Pattern: Bearish Engulfing (Envolvente Bajista)
    # Previous: Green, Current: Red, Current body covers previous body
    df['is_bearish_engulfing'] = (
        (df['close'].shift(1) > df['open'].shift(1)) & # Prev green
        (df['close'] < df['open']) &                  # Curr red
        (df['close'] < df['open'].shift(1)) &         # Red close lower than green open
        (df['open'] > df['close'].shift(1))           # Red open higher than green close
    )
    
    return df


'''

📊 Mejoras para Bollinger Bands y Señales de Compra/Venta

🎯 Estrategias de Señales Específicas


📊 Visualización Mejorada en tu Dashboard
python
# En tu callback de Plotly:
def update_chart(indicadores_activos, tema, n_clicks):
    candles = cargar_datos()
    
    # Filtrar señales de Bollinger Bands
    bb_buy_signals = candles[
        (candles['signal_buy_sell'] == 'buy') & 
        (candles['signal_type'].str.contains('BB_', na=False))
    ]
    bb_sell_signals = candles[
        (candles['signal_buy_sell'] == 'sell') & 
        (candles['signal_type'].str.contains('BB_', na=False))
    ]
    
    fig = go.Figure()
    
    # ... tu código actual de velas ...
    
    # Agregar Bollinger Bands al gráfico
    if 'bollinger' in indicadores_activos:
        # Bandas principales
        fig.add_trace(go.Scatter(
            x=candles['timestamp'], y=candles['bb_upper'],
            line=dict(color='purple', width=1, dash='dash'),
            name='BB Upper'
        ))
        fig.add_trace(go.Scatter(
            x=candles['timestamp'], y=candles['bb_lower'],
            line=dict(color='purple', width=1, dash='dash'),
            name='BB Lower',
            fill='tonexty'
        ))
        fig.add_trace(go.Scatter(
            x=candles['timestamp'], y=candles['bb_middle'],
            line=dict(color='blue', width=1),
            name='BB Middle'
        ))
    
    # Agregar señales BB específicas
    if 'signals' in indicadores_activos:
        if not bb_buy_signals.empty:
            fig.add_trace(go.Scatter(
                x=bb_buy_signals['timestamp'], 
                y=bb_buy_signals['close'],
                mode='markers',
                marker=dict(color='lime', symbol='circle', size=10),
                name='Compra BB'
            ))
        
        if not bb_sell_signals.empty:
            fig.add_trace(go.Scatter(
                x=bb_sell_signals['timestamp'], 
                y=bb_sell_signals['close'],
                mode='markers',
                marker=dict(color='magenta', symbol='x', size=10),
                name='Venta BB'
            ))
    
    return fig
🎯 Resumen de Mejoras
Múltiples bandas (1std y 2std)

Indicadores derivados (%B, Bandwidth, Position)

4 estrategias diferentes de trading

Señales priorizadas y limpiadas

Flexibilidad para usar estrategias específicas

Integración perfecta con tu código existente

'''