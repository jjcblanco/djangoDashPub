'''


'''
import ccxt
import json
import math

# mis libs
from . import config
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

binance = ccxt.binance()
exchange = binance
binance.load_markets()
#print("ahora imprimo los simbolos")
#print(binance.symbols)
#print("ahora imprimo los exchanges soportados")
#print_exchanges()
binance.apiKey=config.BINANCE_APIKEY
binance.secret=config.BINANCE_SECRET
print(binance.check_required_credentials())
balance =binance.fetch_balance()
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
    # signals from supertrend indicator
    df['signal_buy_sell']='none'
    if 'signal_strenght' not in df.columns:
        df['signal_strenght'] = 0

    for current in range(1, len(df.index)):
        previous = current - 1
        current_strength = df['signal_strenght'].iloc[current]
        if not df['in_uptrend'][previous] and df['in_uptrend'][current]:
            df['signal_buy_sell'][current]='buy'
            df['signal_strenght'][current]=current_strength+1
        if df['in_uptrend'][previous] and not df['in_uptrend'][current]:
            df['signal_buy_sell'][current]='sell'
            df['signal_strenght'][current]=current_strength+1
    
    # Señales RSI
    df = generate_rsi_signals(df)

    # Ichimoku Analisis de tendencias
    df['tendencia_ichi'] = np.nan
    for current in range(1, len(df.index)):
        previous = current -1
        if df['senkou_a'][current] < df['senkou_b'][current] and df['senkou_a'][previous] > df['senkou_b'][previous]:
            df['tendencia_ichi'][current] = 'uptrend'
        if df['senkou_a'][current] > df['senkou_b'][current] and df['senkou_a'][previous] < df['senkou_b'][previous]:
            df['tendencia_ichi'][current] = 'downtrend'
    
    # ichicmoku cruce se tenkan-sen kijun-sen
    print("analisis de cruces de tenkan y kinjun")
    for current in range(1, len(df.index)):
            previous = current - 1
            if (not math.isnan(df['tenkan'][previous]))  and (not math.isnan(df['kijun'][previous])) and (not math.isnan(df['tenkan'][current])) and (not math.isnan(df['kijun'][current])):
                if ((df['kijun'][previous] > df['tenkan'][previous]) and (df['tenkan'][current] > df['kijun'][current])):
                    print("Timestamp",df['timestamp'][current]," Kijun",df['kijun'][current], "   Tenkan", df['tenkan'][current])                #if ((df['kijun'][previous] < df['tenkan'][previous]) and (df['tenkan'][current] < df['kijun'][current])):
                    #print(df['tenkan'])

    return(df)
def table(df):

    # Connect to the MySQL server
    cnx = mysql.connector.connect(user='root', password='retsam77', host='10.120.1.124', database='tbot')

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
   cnx = mysql.connector.connect(user='root', password='retsam77', host='192.168.0.181', database='tbot')
   cursor = cnx.cursor()
   engine = create_engine('mysql+mysqlconnector://root:retsam77@192.168.0.181/tbot')
   df.to_sql('df_data', engine, if_exists='replace', index=False)
   cursor.close()
   cnx.close()
     
def historical_fetch_ohlcv(pair,date_from,timeframe):
    from_ts = binance.parse8601(date_from)
    ohlcv_list = []
    ohlcv = binance.fetch_ohlcv(pair, timeframe, since=from_ts, limit=1000)
    ohlcv_list.append(ohlcv)
    while True:
        from_ts = ohlcv[-1][0]
        new_ohlcv = binance.fetch_ohlcv(pair, timeframe, since=from_ts, limit=1000)
        ohlcv.extend(new_ohlcv)
        if len(new_ohlcv)!=1000:
    	    break
    return(ohlcv)


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
    return(sig)

#schedule.every(10).seconds.do(run_bot)

#while True:
    #schedule.run_pending()
    #time.sleep(1)
