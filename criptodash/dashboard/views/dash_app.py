"""
Aplicación Dash para análisis técnico interactivo.

Este módulo contiene la aplicación Dash completa con su layout y callbacks
para visualización interactiva de indicadores técnicos.
"""

from django_plotly_dash import DjangoDash
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from dash import dcc, html, Input, Output

# Crear aplicación Dash
app = DjangoDash('TechnicalAnalysisDashboard')


def cargar_datos():
    """Genera datos de prueba para el gráfico"""
    np.random.seed(42)
    dates = pd.date_range('2023-01-01', periods=100, freq='D')
    
    return pd.DataFrame({
        'timestamp': dates,
        'open': np.random.normal(100, 5, 100),
        'high': np.random.normal(105, 4, 100),
        'low': np.random.normal(95, 4, 100),
        'close': np.random.normal(102, 3, 100),
        'tenkan': np.random.normal(101, 2, 100),
        'kijun': np.random.normal(100, 1.5, 100),
        'senkou_a': np.random.normal(103, 2, 100),
        'senkou_b': np.random.normal(99, 2, 100),
        'senkou_c': np.random.normal(101, 1.5, 100),
        'upperband': np.random.normal(107, 3, 100),
        'lowerband': np.random.normal(97, 3, 100),
        'UpperBollBand': np.random.normal(108, 2, 100),
        'LowerBollBand': np.random.normal(96, 2, 100),
        'signal_buy_sell': np.random.choice(['', 'buy', 'sell'], 100, p=[0.7, 0.15, 0.15])
    })


# Layout de la aplicación Dash
app.layout = html.Div([
    dcc.Store(id='api-data-store'),
    html.Div([
        # Contenedor grid con dos columnas arriba y gráfico abajo
        html.Div([
            # Columna 1 - Indicadores
            html.Div([
                html.H4("📊 INDICADORES TÉCNICOS", style={
                    'textAlign': 'center', 
                    'color': '#ecf0f1',
                    'marginBottom': '15px',
                    'fontSize': '14px'
                }),
                
                html.Div([
                    dcc.Checklist(
                        id='indicadores-checklist',
                        options=[
                            {'label': ' Velas Japonesas', 'value': 'candlestick'},
                            {'label': ' Tenkan-sen (Conversion)', 'value': 'tenkan'},
                            {'label': ' Kijun-sen (Base)', 'value': 'kijun'},
                            {'label': ' Senkou Span A', 'value': 'senkou_a'},
                            {'label': ' Senkou Span B', 'value': 'senkou_b'},
                            {'label': ' Chikou Span', 'value': 'chikou'},
                            {'label': ' Señales Buy/Sell', 'value': 'signals'},
                            {'label': ' Supertrend', 'value': 'supertrend'},
                            {'label': ' Bollinger Bands', 'value': 'bollinger'}
                        ],
                        value=['candlestick', 'tenkan', 'kijun', 'signals'],
                        style={
                            'fontSize': '12px',
                            'color': '#ecf0f1',
                            'display': 'grid',
                            'gridTemplateColumns': '1fr 1fr',
                            'gap': '8px'
                        }
                    )
                ], style={'maxHeight': '200px', 'overflowY': 'auto'})
                
            ], style={
                'gridArea': 'indicadores',
                'background': '#2c3e50',
                'padding': '15px',
                'borderRadius': '8px'
            }),
            
            # Columna 2 - Apariencia y Controles
            html.Div([
                html.H4("🎨 APARIENCIA & CONTROLES", style={
                    'textAlign': 'center', 
                    'color': '#ecf0f1',
                    'marginBottom': '15px',
                    'fontSize': '14px'
                }),
                
                html.Div([
                    html.Label("Tema de visualización:", style={
                        'fontSize': '12px',
                        'fontWeight': 'bold',
                        'color': '#ecf0f1',
                        'marginBottom': '8px'
                    }),
                    
                    dcc.RadioItems(
                        id='theme-selector',
                        options=[
                            {'label': ' 🕶️ Oscuro', 'value': 'plotly_dark'},
                            {'label': ' ☀️ Claro', 'value': 'plotly_white'},
                            {'label': ' 📋 Grid', 'value': 'plotly'},
                            {'label': ' 🎯 Presentación', 'value': 'presentation'}
                        ],
                        value='plotly_dark',
                        style={
                            'fontSize': '11px',
                            'color': '#ecf0f1',
                            'display': 'flex',
                            'flexDirection': 'row',
                            'gap': '5px',
                            'marginBottom': '15px'
                        }
                    ),
                    
                    html.Label("Opciones de visualización:", style={
                        'fontSize': '12px',
                        'fontWeight': 'bold',
                        'color': '#ecf0f1',
                        'marginBottom': '8px'
                    }),
                    
                    dcc.Checklist(
                        id='visual-options',
                        options=[
                            {'label': ' 📊 Mostrar grid', 'value': 'show_grid'},
                            {'label': ' 📝 Mostrar leyenda', 'value': 'show_legend'},
                            {'label': ' 🎚️ Rangeslider', 'value': 'show_rangeslider'},
                            {'label': ' 🔍 Zoom habilitado', 'value': 'enable_zoom'}
                        ],
                        value=['show_grid', 'show_legend', 'enable_zoom'],
                        style={
                            'fontSize': '11px',
                            'color': '#ecf0f1',
                            'display': 'flex',
                            'flexDirection': 'row',
                            'gap': '5px',
                            'marginBottom': '15px'
                        }
                    ),
                    
                    html.Div([
                        html.Button(
                            "🔄 Actualizar Gráfico",
                            id="update-button",
                            n_clicks=0,
                            style={
                                'width': '100%',
                                'padding': '10px',
                                'background': '#3498db',
                                'color': 'white',
                                'border': 'none',
                                'borderRadius': '5px',
                                'fontSize': '12px',
                                'cursor': 'pointer',
                                'marginBottom': '8px'
                            }
                        ),
                        
                        html.Button(
                            "🗑️ Limpiar Selección",
                            id="reset-button",
                            n_clicks=0,
                            style={
                                'width': '100%',
                                'padding': '10px',
                                'background': '#e74c3c',
                                'color': 'white',
                                'border': 'none',
                                'borderRadius': '5px',
                                'fontSize': '12px',
                                'cursor': 'pointer'
                            }
                        )
                    ])
                    
                ])
                
            ], style={
                'gridArea': 'apariencia',
                'background': '#34495e',
                'padding': '15px',
                'borderRadius': '8px'
            }),
            
            # Gráfico (ocupa el ancho completo debajo)
            html.Div([
                dcc.Graph(
                    id='technical-chart',
                    config={
                        'displayModeBar': True,
                        'displaylogo': False,
                        'modeBarButtonsToAdd': [
                            'drawline', 
                            'drawopenpath', 
                            'drawclosedpath',
                            'eraseshape'
                        ]
                    },
                    style={
                        'height': '65vh',
                        'width': '100%',
                        'border': '2px solid #95a5a6',
                        'borderRadius': '8px',
                        'background': 'white'
                    }
                )
            ], style={
                'gridArea': 'grafico',
                'padding': '10px'
            })
            
        ], style={
            'display': 'grid',
            'gridTemplateAreas': '''
                "indicadores apariencia"
                "grafico grafico"
            ''',
            'gridTemplateColumns': '1fr 1fr',
            'gridTemplateRows': 'auto 1fr',
            'gap': '20px',
            'width': '100%',
            'minHeight': '80vh'
        })
        
    ], style={
        'padding': '20px',
        'backgroundColor': '#ecf0f1',
        'minHeight': '100vh'
    })
])


# Cliente: cuando se pulsa "update-button" hace fetch al endpoint y guarda respuesta en api-data-store
app.clientside_callback(
    """
    function(n_clicks) {
        if (!n_clicks) {
            return window.dash_clientside.no_update;
        }
        const params = new URLSearchParams({pair: 'ETH/USDT', timeframe: '1m'});
        const url = '/dashboard/api/run-bot/?' + params.toString();
        return fetch(url)
            .then(function(response) { return response.json(); })
            .then(function(data) { return data; })
            .catch(function(err) { console.error('Fetch error:', err); return null; });
    }
    """,
    Output('api-data-store', 'data'),
    Input('update-button', 'n_clicks')
)


# Callback principal: actualiza el gráfico con datos del store o datos de prueba
@app.callback(
    Output('technical-chart', 'figure'),
    [Input('api-data-store', 'data'),
     Input('indicadores-checklist', 'value'),
     Input('theme-selector', 'value'),
     Input('update-button', 'n_clicks')]
)
def update_chart(api_data, indicadores_activos, tema, n_clicks):
    """Actualiza el gráfico técnico basado en los datos y configuración seleccionada"""
    # Usar datos desde API si vienen
    try:
        if api_data:
            candles = pd.DataFrame(api_data)
            if 'timestamp' in candles.columns:
                candles['timestamp'] = pd.to_datetime(candles['timestamp'])
        else:
            candles = cargar_datos()
    except Exception:
        candles = cargar_datos()

    buy_signals = candles[candles.get('signal_buy_sell', '') == "buy"] if 'signal_buy_sell' in candles.columns else candles[candles.get('signal_buy_sell', '') == "buy"]
    sell_signals = candles[candles.get('signal_buy_sell', '') == "sell"] if 'signal_buy_sell' in candles.columns else candles[candles.get('signal_buy_sell', '') == "sell"]

    fig = go.Figure()
    if 'candlestick' in indicadores_activos:
        fig.add_trace(go.Candlestick(
            x=candles['timestamp'], open=candles['open'], high=candles['high'],
            low=candles['low'], close=candles['close'], name='Candlestick'
        ))
    
    if 'tenkan' in indicadores_activos:
        fig.add_trace(go.Scatter(x=candles['timestamp'], y=candles['tenkan'], name='Tenkan-sen', line=dict(color='blue')))

    if 'kijun' in indicadores_activos:
        fig.add_trace(go.Scatter(x=candles['timestamp'], y=candles['kijun'], name='Kijun-sen', line=dict(color='red')))

    if 'senkou_a' in indicadores_activos and 'senkou_b' in indicadores_activos:
        # Add Ichimoku cloud fill
        fig.add_trace(go.Scatter(
            x=candles['timestamp'], y=candles['senkou_a'],
            fill='tonexty', mode='lines', line=dict(color='green', width=0),
            fillcolor='rgba(0,255,0,0.3)', name='Ichimoku Cloud'
        ))
        fig.add_trace(go.Scatter(
            x=candles['timestamp'], y=candles['senkou_b'],
            mode='lines', line=dict(color='orange'), name='Senkou Span B'
        ))
    else:
        if 'senkou_a' in indicadores_activos:
            fig.add_trace(go.Scatter(x=candles['timestamp'], y=candles['senkou_a'], name='Senkou Span A', line=dict(color='green')))

        if 'senkou_b' in indicadores_activos:
            fig.add_trace(go.Scatter(x=candles['timestamp'], y=candles['senkou_b'], name='Senkou Span B', line=dict(color='orange')))

    if 'chikou' in indicadores_activos:
        fig.add_trace(go.Scatter(x=candles['timestamp'], y=candles['senkou_c'], name='Chikou Span', line=dict(color='purple')))
    
    if 'signals' in indicadores_activos:
        fig.add_trace(go.Scatter(x=buy_signals['timestamp'], y=buy_signals['close'], mode='markers', 
                               marker=dict(color='green', symbol='triangle-up', size=10), name='Buy Signal'))
        fig.add_trace(go.Scatter(x=sell_signals['timestamp'], y=sell_signals['close'], mode='markers', 
                               marker=dict(color='red', symbol='triangle-down', size=10), name='Sell Signal'))
    
    if 'supertrend' in indicadores_activos:
        fig.add_trace(go.Scatter(x=candles['timestamp'], y=candles['upperband'], line=dict(color='yellow', width=2), name='Supertrend Upper'))
        fig.add_trace(go.Scatter(x=candles['timestamp'], y=candles['lowerband'], line=dict(color='yellow', width=2), name='Supertrend Lower'))
    
    if 'bollinger' in indicadores_activos:
        fig.add_trace(go.Scatter(x=candles['timestamp'], y=candles['UpperBollBand'], line=dict(color='purple', width=2), name='Bollinger Upper'))
        fig.add_trace(go.Scatter(x=candles['timestamp'], y=candles['LowerBollBand'], line=dict(color='purple', width=2), name='Bollinger Lower'))
    
    fig.update_layout(
        title='ANÁLISIS TÉCNICO - DASHBOARD',
        xaxis_title='FECHA', yaxis_title='PRECIO',
        template=tema, xaxis_rangeslider_visible=False,
        showlegend=True, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=10, r=10, t=50, b=10)  # Márgenes más ajustados
    )

    # Ajustar eje Y dinámicamente para el gráfico del Dash
    try:
        y_vals = []
        if 'low' in candles.columns and 'high' in candles.columns:
            y_vals.append(candles['low'].min())
            y_vals.append(candles['high'].max())
        # incluir señales si existen
        if not buy_signals.empty:
            y_vals.append(buy_signals['close'].min())
            y_vals.append(buy_signals['close'].max())
        if not sell_signals.empty:
            y_vals.append(sell_signals['close'].min())
            y_vals.append(sell_signals['close'].max())
        if y_vals:
            y_min = float(min(y_vals))
            y_max = float(max(y_vals))
            padding = (y_max - y_min) * 0.05 if (y_max - y_min) > 0 else max(abs(y_max), 1.0) * 0.01
            fig.update_yaxes(range=[y_min - padding, y_max + padding], automargin=True)
        else:
            fig.update_yaxes(autorange=True)
    except Exception:
        fig.update_yaxes(autorange=True)
    
    return fig
