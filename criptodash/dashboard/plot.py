from plotly.subplots import make_subplots
import plotly.graph_objects as go
import pandas as pd

#Orden de graficos
# Candlestick
# Ichimoku ---- Tenkan-sen
# Ichimoku ---- Kijun-sen
# Ichimoku ---- Senkou Span A
# Ichimoku ---- Senkou Span B
# Ichimoku ---- Chikou Span


def plotear(candles):
    
     # format the data to match the charting library
    # filtra el dataset para quedarse con las filas que tengan señal buy o sell
    buy_signals = candles[candles['signal_buy_sell'] == "buy"]
    sell_signals = candles[candles['signal_buy_sell'] == "sell"]
    

    fig =go.Figure(data=[go.Candlestick(x=candles['timestamp'],
                                        open=candles['open'], high=candles['high'],
                                        low=candles['low'], close=candles['close'],
                                        name='Candlestick')],)
    #fig.set_subplots(rows=2,cols=1)
    #ichimoku
    fig.add_trace(go.Scatter(
        x=candles['timestamp'],
        y=candles['tenkan'],
        name='Tenkan-sen',
        line=dict(color='blue')
    ))
#####
    fig.add_trace(go.Scatter(
        x=candles['timestamp'],
        y=candles['kijun'],
        name='Kijun-sen',
        line=dict(color='red')
    ))

    fig.add_trace(go.Scatter(x=candles['timestamp'], y=buy_signals['close'], mode='markers', marker=dict(color='orange', symbol='triangle-up'), name='Buy Signal'))
    fig.add_trace(go.Scatter(x=candles['timestamp'], y=sell_signals['close'], mode='markers', marker=dict(color='brown', symbol='triangle-down'), name='Sell Signal'))

    
    fig.add_trace(go.Scatter(
        x=candles['timestamp'],
        y=candles['senkou_c'],
        name='------',
        #fill='tozeroy',
        line=dict(color='rgba(255, 255, 255, 0)',width=2)
    ))

    fig.add_trace(go.Scatter(
        x=candles['timestamp'],
        y=candles['senkou_b'],
        name='Senkou Span B',
        fill='tonexty',
        fillcolor='rgba(255, 0, 0, 0.3)',
        line=dict(color='rgba(255, 0, 0, 0.3)',width=2)
    ))
    fig.add_trace(go.Scatter(
            x=candles['timestamp'],
            y=candles['senkou_c'],
            name='------',
            #fill='tozeroy',
            line=dict(color='rgba(255, 255, 255, 0)',width=2)
        ))
    fig.add_trace(go.Scatter(
            x=candles['timestamp'],
            y=candles['senkou_a'],
            name='Senkou Span A',
            fill='tonexty',
            fillcolor='rgba(0, 255, 0, 0.3)',
            line=dict(color='rgba(0, 255, 0, 0.3)',width=2)
        ))

    #fin ichimoku
    
    
    fig.add_trace(go.Scatter(x=candles['timestamp'],
                             y=candles['upperband'],
                             line=dict(color='yellow',width=5),
                             name='Supertrend Upperband'))

    fig.add_trace(go.Scatter(x=candles['timestamp'],
                            y=candles['lowerband'],
                            line=dict(color='yellow',width=4),
                            name='Supertrend Lowerband'))

    fig.add_trace(go.Scatter(x=candles['timestamp'],
                             y=candles['UpperBollBand'],
                             line=dict(color='purple',width=3.5),
                             name='Bollinger Upperband'))

    fig.add_trace(go.Scatter(x=candles['timestamp'],
                            y=candles['LowerBollBand'],
                            line=dict(color='purple',width=2),
                            name='Bollinger Lowerband'))
    
    fig.add_trace(go.Scatter(
        x=candles['timestamp'][candles['tenkan'] > candles['kijun']],
        y=candles['tenkan'][candles['tenkan'] > candles['kijun']],
        mode='markers',
        marker=dict(color='blue', size=10),
        name='Cross'
    ))
    '''fig.append_trace(go.Histogram(x=candles['macd_hist'], 
                             nbinsx=50, 
                             name='Histograma'), row=2, col=1)
    '''
    #fig.append_trace(go.Scatter(x=candles['timestamp'],
    #                        y=candles['macd'],
    #                        line=dict(color='blue'),
    #                        name='MACD'),row=2,col=1)
    
   #fig.append_trace(go.Scatter(x=candles['timestamp'],
    #                        y=candles['signal_macd'],
     #                       line=dict(color='floralwhite'),
      #                      name='MACD'),row=2,col=1)
    
    # customize the appearance of the plot
    fig.update_layout(
        title='Candlestick Chart with Supertrend Upperband',
        xaxis_title='Date',
        yaxis_title='Price',
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        template='plotly_dark',  # use a dark template for a more visually appealing plot
    )
    fig.update_layout(updatemenus=[dict(
    buttons=[
        dict(label='Show All', method='update', args=[{'visible': [True, True,True,True,True,True,True,True,True,True,True,True,True,True]}]),
        dict(label='Hide All', method='update', args=[{'visible': [False,False,False,False, False,False,False,False,False,False,False,False,False,False]}]),
        dict(label='Show candlestick', method='update', args=[{'visible': [True,False,False,False, False,False,False,False,False,False,False,False,False,False]}]),
        dict(label='Show Tenkan-sen', method='update', args=[{'visible': [False,True,False,False, False,False,False,False,False,False,False,False,False]}]),
        dict(label='Show Kijun-sen', method='update', args=[{'visible': [False,False,True,False, False,False,False,False,False,False,False,False,False]}]),
        dict(label='Show Buy Signal', method='update', args=[{'visible': [False,False,False,True, False,False,False,False,False,False,False,False]}]),
        dict(label='Show Sell Signal', method='update', args=[{'visible': [False,False,False,False,True,False,False,False,False,False,False,False]}]),
        dict(label='Show All Signals', method='update', args=[{'visible': [False,False,False,True,True,False,False,False,False,False,False,False]}]),
        dict(label='Show Kijun-sen & Tenkan-sen', method='update', args=[{'visible': [False,True,True,False,False,False,False,False,False,False,False,False,False]}]),
        dict(label='Hide Senkou Span', method='update', args=[{'visible': [False,False,False,False,False,False,False,False,False,False,False,False]}]),
        dict(label='Show Senkou Span', method='update', args=[{'visible': [False,False,False,False,False,True,True,False,False,False,False,False]}]),
        dict(label='Show Supertrend Bands', method='update', args=[{'visible': [False,False,False,False,False,False,False,False,False,True,True,False,False,False]}]),
        dict(label='Hide Supertrend Bands', method='update', args=[{'visible': [False,False,False,False,False,False,False,False,False,False,False,False]}]),
        dict(label='Show Supertrend Lowerband', method='update', args=[{'visible': [False,False,False,False,False,False,False,False,False,False,True,False,False,False]}]),
        dict(label='Show Bollinger Upperband', method='update', args=[{'visible': [False,False,False,False,False,False,False,False,False,False,False,True,False,False]}]),
        dict(label='Show Bollinger Lowerband' ,method='update', args=[{'visible': [False,False,False,False,False,False,False,False,False,False,False,False,True,False]}]),
        dict(label='Show  Cross' ,method='update', args=[{'visible': [False,False,False,False,False,False,False,False,False,False,False,False,False,True]}])
    ],
    direction='down',
    pad={'r': 10, 't': 20},
    showactive=True,
    x=0.9,
    xanchor='left',
    y=1.4,
    yanchor='top'
)])

    fig.update_xaxes(tickformat='%Y-%m-%d %H:%M:%S')  # format x-axis labels as datetime
    
    fig.update_xaxes(showgrid=True, gridcolor='lightgrey', gridwidth=1)  # show gridlines on x-axis
    fig.update_yaxes(showgrid=True, gridcolor='lightgrey', gridwidth=1)  # show gridlines on y-axis
    
    
    
    fig.show()
    
    # add the MACD indicator
    '''fig.add_trace(go.Scatter(x=candles['timestamp'],
                          y=candles['macd'],
                          line=dict(color='blue'),
                          name='MACD'))
'''
