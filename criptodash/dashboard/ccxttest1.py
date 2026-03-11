'''


'''
import ccxt
import json
import math

# mis libs
from django.conf import settings
from . import estilos
from .indicadores import *

#fin mis libs
import mysql.connector
from sqlalchemy import create_engine,types
#from TVPlot import chartear
import schedule
from pprint import pprint
import pandas as pd
pd.set_option('display.max_rows', None)

import warnings
warnings.filterwarnings('ignore')

import numpy as np
from datetime import datetime
import time
from .plot import plotear
from .models import Pair

binance = ccxt.binance({
    'options': {
        'recvWindow': 60000,  # Aumentar ventana de recepción a 60 segundos
        'adjustForTimeDifference': True,  # Ajustar automáticamente por diferencia de tiempo
    },
    'apiKey': getattr(settings, 'BINANCE_APIKEY', None),
    'secret': getattr(settings, 'BINANCE_SECRET', None),
})
exchange = binance
_binance_initialized = False

def _ensure_binance_initialized():
    global _binance_initialized
    if not _binance_initialized:
        binance.load_markets()
        print("Markets loaded:", len(binance.markets))
        _binance_initialized = True
# balance =binance.fetch_balance()
#print(type(balance))

#for x,y in balance['free'].items():
#    if y!=0:
#        print(x,y)
#print(json.dumps(balance['used']))

#print(binance.balance())
#print(json.dumps(binance.watch_balance()))

def crear_orden():
    symbol = 'ETH/BTC'
    type = 'limit'  # or 'market'
    side = 'sell'  # or 'buy'
    amount = 1.0
    price = 0.060154  # or None

    # extra params and overrides if needed
    params = {
    'test': True,  # test if it's valid, but don't actually place it
    }

    order = binance.create_order(symbol, type, side, amount, price, params)

    print(order)

def cancelar_orden():
    cancelResponse = exchange.cancel_order(newOrder1['id'])
    print(cancelResponse)

def dump(*args):
   print(' '.join([str(arg) for arg in args]))

# imprime los exchanges soportados

def print_exchanges():
   dump('Supported exchanges:', ', '.join(ccxt.exchanges))

in_position = False

def check_buy_sell_signals(df):
    global in_position

    print("checking for buy and sell signals")
    #print(df.tail(5))
    last_row_index = len(df.index) - 1
    previous_row_index = last_row_index - 1

    if not df['in_uptrend'][previous_row_index] and df['in_uptrend'][last_row_index]:
        print("changed to uptrend, buy")
        if not in_position:
            #order = exchange.create_market_buy_order('ETH/USD', 0.05)
            #print(order)
            in_position = True
        else:
            print("already in position, nothing to do")

    if df['in_uptrend'][previous_row_index] and not df['in_uptrend'][last_row_index]:
        if in_position:
            print("changed to downtrend, sell")
            #order = exchange.create_market_sell_order('ETH/USD', 0.05)
            #print(order)
            in_position = False
        else:
            print("You aren't in position, nothing to sell")

def signals(df):
    """
    Calcula señales de trading con scoring de confluencia y gestión de riesgos refinada.
    """
    # 1. Calcular indicadores base
    df['ema_200'] = ema(df, 200)
    df['obv'] = obv(df)
    df['vwap'] = vwap(df)
    df['adx'] = adx(df)
    df['vol_ma'] = volume_ma(df)
    
    # Asegurar que todos los indicadores requeridos se calculan
    df = supertrend(df)
    df = generate_rsi_signals(df)
    df = ichimoku_cloud(df)
    # bollinger_bands ya se llama si es necesario, pero aquí usamos indicadores específicos
    df = bollinger_bands(df, window=20, num_std=2, generate_signals=True)
    
    # 2. Inicializar columnas de señales
    df['signal_buy_sell'] = 'none'
    if 'signal_strenght' not in df.columns:
        df['signal_strenght'] = 0
    
    df['stop_loss'] = np.nan
    df['take_profit'] = np.nan
    
    # 3. Calcular Scoring de Confluencia
    for current in range(30, len(df.index)): # Empezar un poco después para tener datos de ADX/MA
        previous = current - 1
        score = 0
        signal = 'none'
        
        current_price = df['close'].iloc[current]
        ema_200 = df['ema_200'].iloc[current]
        rsi = df['rsi'].iloc[current]
        current_adx = df['adx'].iloc[current]
        current_vol = df['volume'].iloc[current]
        vol_ma = df['vol_ma'].iloc[current]
        
        # FILTRO CRÍTICO: Fuerza de Tendencia (ADX)
        # No operamos si el mercado está demasiado lateral
        if current_adx < 20:
            continue

        # --- Lógica de COMPRA ---
        # A. Gatillo: Supertrend alcista Y filtro EMA 200 (Tendencia principal)
        if df['in_uptrend'].iloc[current] and current_price > ema_200:
            score += 2 # 2 puntos por alineación de tendencia
            
            # B. Confirmación de Volumen (Pico de volumen)
            if current_vol > vol_ma * 1.2:
                score += 1
                
            # C. RSI favorable (no sobrecomprado, con momentum alcista)
            if 45 < rsi < 70:
                score += 1
                
            # D. OBV subiendo
            if df['obv'].iloc[current] > df['obv'].iloc[previous]:
                score += 0.5
                
            # E. Ichimoku (Precio sobre la nube)
            if 'senkou_a' in df.columns and current_price > max(df['senkou_a'].iloc[current], df['senkou_b'].iloc[current]):
                score += 1
            
            # Requerir al menos 4 puntos (Fuerte confluencia alcista)
            if score >= 4:
                signal = 'buy'

        # --- Lógica de VENTA ---
        # A. Gatillo: Supertrend bajista Y filtro EMA 200 (Tendencia principal)
        elif not df['in_uptrend'].iloc[current] and current_price < ema_200:
            score += 2
            
            # B. Confirmación de Volumen
            if current_vol > vol_ma * 1.2:
                score += 1
                
            # C. RSI favorable (no sobrevendido, con momentum bajista)
            if 30 < rsi < 55:
                score += 1
                
            # D. OBV bajando
            if df['obv'].iloc[current] < df['obv'].iloc[previous]:
                score += 0.5
                
            # E. Ichimoku (Precio bajo la nube)
            if 'senkou_a' in df.columns and current_price < min(df['senkou_a'].iloc[current], df['senkou_b'].iloc[current]):
                score += 1
            
            if score >= 4:
                signal = 'sell'

        # 4. Asignar Señal y Niveles de Riesgo
        if signal != 'none':
            df.at[df.index[current], 'signal_buy_sell'] = signal
            df.at[df.index[current], 'signal_strenght'] = score
            
            # Calcular SL y TP
            sl, tp = calculate_sl_tp(df.iloc[:current+1], signal, atr_multiplier_sl=2.0, atr_multiplier_tp=3.0)
            df.at[df.index[current], 'stop_loss'] = sl.iloc[-1]
            df.at[df.index[current], 'take_profit'] = tp.iloc[-1]

    return df

def table(df):

    # Connect to the MySQL server
    cnx = mysql.connector.connect(
        user=config('DB_USER'),
        password=config('DB_PASSWORD'),
        host='10.120.1.124',
        database='tbot'
    )

    # Create a MySQL table
    cursor = cnx.cursor()

    # Get the list of column names
    column_names = df.columns.tolist()
    #print(column_names)
    # Create the table
    column_names = [column.lower() for column in column_names]
    create_table_query = f"CREATE TABLE df_data ({', '.join([f'{column} VARCHAR(255)' for column in column_names])})"

    cursor.execute(create_table_query)

    # Close the cursor and the connection
    cursor.close()
    cnx.close()
def table_insert(df):
   # Connect to the MySQL server
   cnx = mysql.connector.connect(
       user=config('DB_USER'),
       password=config('DB_PASSWORD'),
       host='192.168.0.181',
       database='tbot'
   )
   cursor = cnx.cursor()
   engine = create_engine(f"mysql+mysqlconnector://{config('DB_USER')}:{config('DB_PASSWORD')}@192.168.0.181/tbot")
   df.to_sql('df_data', engine, if_exists='replace', index=False)
   cursor.close()
   cnx.close()

def historical_fetch_ohlcv(pair, date_from=None, timeframe='1h', since=None, limit=None):
    _ensure_binance_initialized()
    # Support both date_from (positional/keyword) and since (keyword)
    actual_since = since if since is not None else date_from

    
    if actual_since is None:
        # Por defecto los últimos 1000 bars
        return binance.fetch_ohlcv(pair, timeframe, limit=1000)
    
    # Manejar datetime objects
    if hasattr(actual_since, 'strftime'):
        from_ts = int(actual_since.timestamp() * 1000)
    else:
        # Asumir string para parse8601
        try:
            from_ts = binance.parse8601(str(actual_since))
        except Exception:
            # Si ya es un timestamp
            from_ts = int(actual_since)

    ohlcv_list = []
    ohlcv = binance.fetch_ohlcv(pair, timeframe, since=from_ts, limit=1000)
    if not ohlcv:
        return []
        
    ohlcv_list.extend(ohlcv)
    
    # Si pedimos un límite específico y ya lo tenemos, paramos
    if limit and len(ohlcv_list) >= limit:
        return ohlcv_list[:limit]
        
    while True:
        from_ts = ohlcv_list[-1][0] + 1 # +1 para no repetir la última vela
        new_ohlcv = binance.fetch_ohlcv(pair, timeframe, since=from_ts, limit=1000)
        if not new_ohlcv:
            break
        ohlcv_list.extend(new_ohlcv)
        if len(new_ohlcv) != 1000:
            break
        if limit and len(ohlcv_list) >= limit:
            return ohlcv_list[:limit]
            
    return ohlcv_list


def run_bot(pair,date_from,timeframe):
    print(f"Fetching new bars for {datetime.now().isoformat()}")
    #bars = binance.fetch_ohlcv('ETH/USDT', timeframe='1m', limit=100)
    #bars = historical_fetch_ohlcv('ETH/USDT', '2025-10-26 18:15:00','1m')
    bars = historical_fetch_ohlcv(pair, date_from,timeframe)
    print(f"Received {len(bars)} bars")
    df = pd.DataFrame(bars[:-1], columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']) # toma los valores de mercado de el par
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms') # convierte los valores de tiempo del df a valores de tipo datetime

    supertrend_data = supertrend(df)
    print("generando macd")
    macd_data = macd(supertrend_data)
    print("generando bollinger")

    boll= enhanced_bollinger_bands(macd_data, window=20, num_std=2, strategy='all')
    print("generando ichimoku")
    ichi= ichimoku_cloud(boll)
    print("generando senales")
    sig=signals(ichi)
    print("ploteando")
    #plotear(sig)
    #print(df.columns.tolist())

    #print(list(df.columns))
    #print(sig.head())
    #chartear(ichi)
    #print(ichi.head())
    #table(ichi)
    print("insertando en la base")
    #table_insert(ichi)
    #check_buy_sell_signals(supertrend_data)

    # Save signals to database with timeframe
    save_signals_to_db(sig, pair, timeframe)

    return(sig)

def save_signals_to_db(df, pair_symbol, timeframe='1h'):
    """Save trading signals to database"""
    from dashboard.models import TradeSignal, TradingPair, Exchange
    from django.utils import timezone

    try:
        # Get or create exchange
        exchange, _ = Exchange.objects.get_or_create(name='Binance')

        # Get or create trading pair (legacy model)
        pair, _ = TradingPair.objects.get_or_create(
            symbol=pair_symbol,
            exchange=exchange,
            defaults={
                'base_asset': pair_symbol.split('/')[0],
                'quote_asset': pair_symbol.split('/')[1] if '/' in pair_symbol else ''
            }
        )

        # Ensure canonical Pair model exists and use it to link new signals
        try:
            canonical_pair = ensure_pair(pair_symbol, pair_type='spot', exchange=exchange.name)
        except Exception:
            canonical_pair = None

        signals_created = 0
        for idx, row in df.iterrows():
            if row.get('signal_buy_sell') in ['buy', 'sell']:
                # Prepare indicators data
                indicators = {}
                
                def safe_float(val):
                    if pd.isna(val) or np.isinf(val):
                        return None
                    return float(val)

                if 'rsi' in row:
                    v = safe_float(row['rsi'])
                    if v is not None: indicators['rsi'] = v
                if 'in_uptrend' in row and not pd.isna(row['in_uptrend']):
                    indicators['in_uptrend'] = bool(row['in_uptrend'])
                if 'macd' in row:
                    v = safe_float(row['macd'])
                    if v is not None: indicators['macd'] = v
                if 'macd_signal' in row:
                    v = safe_float(row['macd_signal'])
                    if v is not None: indicators['macd_signal'] = v
                if 'obv' in row:
                    v = safe_float(row['obv'])
                    if v is not None: indicators['obv'] = v
                if 'vwap' in row:
                    v = safe_float(row['vwap'])
                    if v is not None: indicators['vwap'] = v
                if 'adx' in row:
                    v = safe_float(row['adx'])
                    if v is not None: indicators['adx'] = v
                if 'vol_ma' in row:
                    v = safe_float(row['vol_ma'])
                    if v is not None: indicators['vol_ma'] = v
                if 'stop_loss' in row:
                    v = safe_float(row['stop_loss'])
                    if v is not None: indicators['stop_loss'] = v
                if 'take_profit' in row:
                    v = safe_float(row['take_profit'])
                    if v is not None: indicators['take_profit'] = v

                # Normalize signal type to match model choices
                signal_type = row['signal_buy_sell'].upper()

                # Determine strength (fall back to 1.0)
                strength = float(row['signal_strenght']) if 'signal_strenght' in row and not pd.isna(row['signal_strenght']) else 1.0

                # Create or get signal (linking both legacy pair and canonical pair)
                defaults = {
                    'price': float(row['close']),
                    'strength': strength,
                    # Use None instead of empty dict to avoid MySQL constraint error
                    'indicators': indicators if indicators else None,
                    'indicator': ','.join(list(indicators.keys())) if indicators else None,
                }
                if canonical_pair:
                    defaults['pair_ref'] = canonical_pair

                signal, created = TradeSignal.objects.get_or_create(
                    pair=pair,
                    timestamp=row['timestamp'],
                    signal_type=signal_type,
                    timeframe=timeframe,
                    defaults=defaults
                )
                print(f"DEBUG DB: Saving {signal_type} for {pair_symbol} at {row['timestamp']} (Created: {created})")
                if created:
                    signals_created += 1

        print(f"Saved {signals_created} new signals to database for {pair_symbol}")

    except Exception as e:
        print(f"Error saving signals to database: {e}")
        import traceback
        traceback.print_exc()

def ensure_pair(symbol, pair_type='spot', exchange=None):
    pair, created = Pair.objects.get_or_create(
        symbol=symbol,
        defaults={
            'base_asset': symbol.split('/')[0],
            'quote_asset': symbol.split('/')[1] if '/' in symbol else None,
            'pair_type': pair_type,
            'exchange': exchange,
        }
    )
    return pair
