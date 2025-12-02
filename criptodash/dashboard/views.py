from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django_plotly_dash import DjangoDash
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from dash import dcc, html, Input, Output, callback
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.utils.safestring import mark_safe
from . import ccxttest1  # module with the bot function
from .backtester import SupertrendStrategy, Backtester  # Import backtesting classes

from plotly.offline import plot

from django.utils import timezone
from datetime import datetime, timedelta

from django.http import JsonResponse

app = DjangoDash('TechnicalAnalysisDashboard')

def ejecutar_analisis_trading(request):
    print("Ejecuta el análisis completo y muestra resultados en el dashboard")
    try:
        # Ejecutar el bot de trading
        resultados = run_bot()
        
        # Convertir a formato para el template
        señales = resultados[resultados['signal_buy_sell'].isin(['buy', 'sell'])]
        
        context = {
            'señales': señales.to_dict('records'),
            'ultima_actualizacion': pd.Timestamp.now(),
            'total_señales': len(señales),
            'señales_compra': len(señales[señales['signal_buy_sell'] == 'buy']),
            'señales_venta': len(señales[señales['signal_buy_sell'] == 'sell']),
        }
        
        return render(request, 'trading_bot/resultados.html', context)
    
    except Exception as e:
        return render(request, 'trading_bot/error.html', {'error': str(e)})

def cargar_datos():
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


'''  59x52x4.4'''

# Eliminada la callback duplicada 'update_chart' (se conserva la versión unificada
# más abajo que usa 'api-data-store' y hace fallback a cargar_datos()).
# (La definición anterior @app.callback(... def update_chart(...): ...) fue borrada aquí)

# Callback: ahora usa datos del store si existen (sino caerá en cargar_datos())
@app.callback(
    Output('technical-chart', 'figure'),
    [Input('api-data-store', 'data'),
     Input('indicadores-checklist', 'value'),
     Input('theme-selector', 'value'),
     Input('update-button', 'n_clicks')]
)
def update_chart(api_data, indicadores_activos, tema, n_clicks):
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

# Vista Django tradicional
def index(request):
    if not request.user.is_authenticated:
        return render(request, 'dashboard/index.html')
    return render(request, 'dashboard/index.html', {'user': request.user})
def technical_analysis(request):
    context = {
        'page_title': 'Análisis Técnico Avanzado',
        'active_tab': 'technical'
    }
    return render(request, 'dashboard/index.html', context)

@require_http_methods(["GET", "POST"])
def run_bot_view(request):
    table_html = None
    if request.method == "POST":
        try:
            # Use a date in the past (30 days ago)
            from datetime import datetime, timedelta
            date_from = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')
            # adjust function name if ccxttest1 uses a different name
            result = ccxttest1.run_bot('ETH/USDT', date_from,'1m')
            if hasattr(result, "to_html"):
                table_html = result.to_html(classes="table table-sm table-striped", index=False, border=0)
            else:
                import pandas as pd
                df = pd.DataFrame(result)
                table_html = df.to_html(classes="table table-sm table-striped", index=False, border=0)
            messages.success(request, "Bot ejecutado correctamente")
        except Exception as e:
            messages.error(request, f"Error al ejecutar bot: {e}")
    return render(request, "dashboard/bot_run.html", {"table_html": mark_safe(table_html) if table_html else None})

@require_http_methods(["GET", "POST"])
def import_data(request):
    table_html = None
    if request.method == "POST":
        try:
            result = ccxttest1.run_bot('ETH/USDT', '2025-11-16 18:15:00','1m')
            print(result)
            if hasattr(result, "to_html"):
                
                table_html = result.to_html(classes="table table-sm table-striped", index=False, border=0)
            else:
                print("entro aca")
                import pandas as pd
                df = pd.DataFrame(result)
                table_html = df.to_html(classes="table table-sm table-striped", index=False, border=0)

            messages.success(request, "Datos importados correctamente")
        except Exception as e:
            messages.error(request, f"Error al importar datos: {e}")
    return render(request, "dashboard/bot_run.html", {"table_html": mark_safe(table_html) if table_html else None})

@login_required
def dashboard_mejorado(request):
    print("ejecutando sdashboard_mejorado")
    pair_symbol = request.GET.get('pair', 'ETH/USDT')
    fecha_inicio = request.GET.get('fecha_inicio')
    fecha_fin = request.GET.get('fecha_fin')

    try:
        from .models import TradingPair, TradeSignal
        pair = TradingPair.objects.get(symbol=pair_symbol)

        # Filtrar señales por par
        señales = TradeSignal.objects.filter(pair=pair).order_by('-timestamp')

        # Aplicar filtro de fechas si se proporcionan
        if fecha_inicio:
            from django.utils import timezone
            from datetime import datetime
            try:
                fecha_inicio_dt = timezone.make_aware(datetime.strptime(fecha_inicio, '%Y-%m-%d'))
                señales = señales.filter(timestamp__gte=fecha_inicio_dt)
            except ValueError:
                pass  # Si la fecha no es válida, ignorar el filtro

        if fecha_fin:
            from django.utils import timezone
            from datetime import datetime, timedelta
            try:
                # Agregar un día al fecha_fin para incluir todo el día
                fecha_fin_dt = timezone.make_aware(datetime.strptime(fecha_fin, '%Y-%m-%d')) + timedelta(days=1)
                señales = señales.filter(timestamp__lt=fecha_fin_dt)
            except ValueError:
                pass  # Si la fecha no es válida, ignorar el filtro

    except TradingPair.DoesNotExist:
        print("El par no existe en la base de datos")
        señales = TradeSignal.objects.none()

    # Calcular estadísticas
    from .data_service import calcular_estadisticas_desde_señales
    
    stats = calcular_estadisticas_desde_señales(señales)

    # Generar gráfico
    from .data_service import generar_grafico_desde_señales
    grafico = generar_grafico_desde_señales(señales, pair_symbol)

    # Pasar lista de pairs al template para el selector
    pairs = TradingPair.objects.all().order_by('symbol')

    context = {
        'señales': señales,
        'pairs': pairs,
        'pair_selected': pair_symbol,
        'fecha_inicio': fecha_inicio,
        'fecha_fin': fecha_fin,
        'stats': stats,
        'grafico': grafico,
        'fuente_datos': 'Base de datos local'
    }

    return render(request, 'dashboard/dashboard_mejorado.html', context)


def generar_datos_grafico_desde_señales(señales, fecha_inicio, fecha_fin):
    """Genera datos básicos para el gráfico cuando no hay datos de API"""
    if not señales:
        return pd.DataFrame()
    
    # Crear un DataFrame básico usando las señales como puntos de referencia
    puntos_tiempo = []
    
    for señal in señales:
        timestamp = señal['timestamp'] if isinstance(señal, dict) else señal.timestamp
        precio = señal['price'] if isinstance(señal, dict) else señal.price
        
        puntos_tiempo.append({
            'timestamp': timestamp,
            'open': precio,
            'high': precio * 1.01,
            'low': precio * 0.99,
            'close': precio,
            'volume': 1000
        })
    
    if puntos_tiempo:
        df = pd.DataFrame(puntos_tiempo)
        df = df.sort_values('timestamp')
        return df
    else:
        return pd.DataFrame()
def crear_grafico_con_señales(df, señales, pair='ETH/USDT'):
     """Crea un gráfico Plotly con velas y señales (mejorado: interactividad y señales ligeras)"""
     import numpy as _np
 
     fig = go.Figure()
 
     # Verificar que tenemos datos
     if len(df) == 0:
         fig.add_annotation(text="No hay datos para el período seleccionado", 
                           xref="paper", yref="paper", x=0.5, y=0.5, 
                           showarrow=False, font=dict(size=20))
         # Layout mínimo interactivo
         fig.update_layout(
             template='plotly_dark',
             dragmode='zoom',
             hovermode='closest'
         )
         return fig
 
     # Gráfico de velas (base)
     # Usar hovertext + hoverinfo porque hovertemplate no está disponible para Candlestick en esta versión
     fig.add_trace(go.Candlestick(
         x=df['timestamp'],
         open=df['open'],
         high=df['high'],
         low=df['low'],
         close=df['close'],
         name='Precio',
         increasing=dict(line=dict(color='#00cc96')),
         decreasing=dict(line=dict(color='#ef553b')),
         legendgroup='price',
         hoverinfo='text',
         hovertext=[
             f"Fecha: {pd.to_datetime(ts)}<br>Abrir: {o:.4f}<br>Cerrar: {c:.4f}<br>Alto: {h:.4f}<br>Bajo: {l:.4f}"
             for ts, o, c, h, l in zip(df['timestamp'], df['open'], df['close'], df['high'], df['low'])
         ]
     ))
 
     # Bollinger Bands (si existen) — dibujadas detrás de las señales
     if 'bb_upper' in df.columns and 'bb_lower' in df.columns:
         fig.add_trace(go.Scatter(
             x=df['timestamp'], y=df['bb_upper'],
             line=dict(color='rgba(200,0,0,0.6)', width=1, dash='dash'),
             name='BB Upper',
             fill=None,
             opacity=0.6,
             legendgroup='bb',
         ))
         fig.add_trace(go.Scatter(
             x=df['timestamp'], y=df['bb_lower'],
             line=dict(color='rgba(0,150,0,0.6)', width=1, dash='dash'),
             name='BB Lower',
             fill='tonexty',
             fillcolor='rgba(200,200,200,0.05)',
             opacity=0.6,
             legendgroup='bb',
         ))
 
     # Preparar señales: construir arrays y desplazar ligeramente para no tapar velas
     compras_x, compras_y, compras_strength = [], [], []
     ventas_x, ventas_y, ventas_strength = [], [], []
     for s in señales:
         ts = s.timestamp if hasattr(s, 'timestamp') else s['timestamp']
         price = s.price if hasattr(s, 'price') else s['price']
         strength = s.signal_strength if hasattr(s, 'signal_strength') else s.get('signal_strength', 1)
         typ = s.signal_type if hasattr(s, 'signal_type') else s['signal_type']
 
         # Desplazamiento proporcional a la fuerza para evitar solapado
         offset = float(strength) * 0.002  # 0.2% por unidad de fuerza
         if typ == 'buy':
             compras_x.append(ts)
             compras_y.append(price * (1 - offset))
             compras_strength.append(strength)
         else:
             ventas_x.append(ts)
             ventas_y.append(price * (1 + offset))
             ventas_strength.append(strength)
 
     # Señales de COMPRA (verde) — más discretas
     if compras_x:
         fig.add_trace(go.Scatter(
             x=compras_x, y=compras_y,
             mode='markers+text',
             marker=dict(
                 color='green',
                 size=[max(6, min(6 + s*2, 14)) for s in compras_strength],  # más pequeñas
                 symbol='triangle-up',
                 line=dict(width=1, color='darkgreen'),
                 opacity=0.9
             ),
             text=[f'{s}' for s in compras_strength],
             textposition="top center",
             name='Señal Compra',
             hovertemplate='Compra<br>%{x}<br>Precio: %{y:.4f}<br>F: %{text}<extra></extra>',
             legendgroup='signals',
             showlegend=True
         ))
 
     # Señales de VENTA (rojo)
     if ventas_x:
         fig.add_trace(go.Scatter(
             x=ventas_x, y=ventas_y,
             mode='markers+text',
             marker=dict(
                 color='red',
                 size=[max(6, min(6 + s*2, 14)) for s in ventas_strength],
                 symbol='triangle-down',
                 line=dict(width=1, color='darkred'),
                 opacity=0.9
             ),
             text=[f'{s}' for s in ventas_strength],
             textposition="bottom center",
             name='Señal Venta',
             hovertemplate='Venta<br>%{x}<br>Precio: %{y:.4f}<br>F: %{text}<extra></extra>',
             legendgroup='signals',
             showlegend=True
         ))
 
     # Opciones de layout para interactividad tipo TradingView
     fig.update_layout(
         title=f'Análisis de Trading {pair} con Señales',
         xaxis=dict(
             title='Fecha',
             rangeslider=dict(visible=True),
             rangeselector=dict(
                 buttons=list([
                     dict(count=1, label="1d", step="day", stepmode="backward"),
                     dict(count=7, label="7d", step="day", stepmode="backward"),
                     dict(count=1, label="1m", step="month", stepmode="backward"),
                     dict(step="all")
                 ])
             ),
             type='date'
         ),
         yaxis=dict(title='Precio (USDT)'),
         template='plotly_white',
         hovermode='x unified',
         dragmode='zoom',
         legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
         margin=dict(l=10, r=10, t=50, b=10),
         modebar=dict(remove=[]),
         height=650
     )

    # Mejorar comportamiento al hacer click en la leyenda (toggle/isolate)
     fig.update_layout(legend_itemclick="toggle", legend_itemdoubleclick="toggleothers")

    # Ajustar eje Y en función de los datos visibles (velas + señales) con padding
     try:
            y_vals = []
            if 'low' in df.columns:
                y_vals.append(df['low'].min())
            if 'high' in df.columns:
                y_vals.append(df['high'].max())
            # incluir valores de señales desplazadas si existen
            if compras_y:
                y_vals.extend([min(compras_y), max(compras_y)])
            if ventas_y:
                y_vals.extend([min(ventas_y), max(ventas_y)])
            if y_vals:
                y_min = float(min(y_vals))
                y_max = float(max(y_vals))
                if y_max - y_min > 0:
                    padding = (y_max - y_min) * 0.05
                else:
                    padding = max(abs(y_max), 1.0) * 0.01
                fig.update_yaxes(range=[y_min - padding, y_max + padding], automargin=True)
            else:
                fig.update_yaxes(autorange=True)
     except Exception:
            # fallback a autorange si algo falla
            fig.update_yaxes(autorange=True)

     return fig

def calcular_estadisticas(df, señales):
    """Calcula estadísticas del período"""
    if len(df) == 0:
        return {
            'total_señales': 0,
            'compras': 0,
            'ventas': 0,
            'fuerza_promedio': 0,
            'precio_max': 0,
            'precio_min': 0,
            'volumen_promedio': 0,
        }
    
    señales_list = list(señales)
    
    return {
        'total_señales': len(señales_list),
        'compras': len([s for s in señales_list if (
            s.signal_type == 'buy' if hasattr(s, 'signal_type') else s.get('signal_type') == 'buy'
        )]),
        'ventas': len([s for s in señales_list if (
            s.signal_type == 'sell' if hasattr(s, 'signal_type') else s.get('signal_type') == 'sell'
        )]),
        'fuerza_promedio': sum(
            s.signal_strength if hasattr(s, 'signal_strength') else s.get('signal_strength', 0) 
            for s in señales_list
        ) / len(señales_list) if señales_list else 0,
        'precio_max': df['high'].max(),
        'precio_min': df['low'].min(),
        'volumen_promedio': df['volume'].mean() if 'volume' in df.columns else 0,
    }


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

# Callback: ahora usa datos del store si existen (sino caerá en cargar_datos())
@app.callback(
    Output('technical-chart', 'figure'),
    [Input('api-data-store', 'data'),
     Input('indicadores-checklist', 'value'),
     Input('theme-selector', 'value'),
     Input('update-button', 'n_clicks')]
)
def update_chart(api_data, indicadores_activos, tema, n_clicks):
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

# Nuevo endpoint JSON que ejecuta ccxttest1.run_bot y devuelve lista de registros
def run_bot_api(request):
    pair = request.GET.get('pair', 'ETH/USDT')
    date_from = request.GET.get('date_from')  # optional
    timeframe = request.GET.get('timeframe', '1m')

    try:
        # Intentar varias firmas comunes
        try:
            result = ccxttest1.run_bot(pair=pair, date_from=date_from, timeframe=timeframe)
        except TypeError:
            try:
                result = ccxttest1.run_bot(pair, date_from, timeframe)
            except Exception:
                result = ccxttest1.run_bot()

        # Normalizar salida a una lista de dicts
        if hasattr(result, "to_dict"):
            data = result.to_dict('records')
        elif isinstance(result, list):
            data = result
        else:
            try:
                df = pd.DataFrame(result)
                data = df.to_dict('records')
            except Exception:
                data = {'result': str(result)}

        safe_flag = isinstance(data, dict)
        return JsonResponse(data, safe=safe_flag)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def backtest_view(request):
    """Vista para ejecutar backtests"""
    if request.method == 'POST':
        try:
            pair_symbol = request.POST.get('pair', 'ETH/USDT')
            start_date_str = request.POST.get('start_date')
            end_date_str = request.POST.get('end_date')
            initial_balance = float(request.POST.get('initial_balance', 10000))

            # Convertir fechas
            start_date = timezone.make_aware(datetime.strptime(start_date_str, '%Y-%m-%d'))
            end_date = timezone.make_aware(datetime.strptime(end_date_str, '%Y-%m-%d'))

            # Crear estrategia y backtester
            strategy = SupertrendStrategy()
            backtester = Backtester(initial_balance=initial_balance)

            # Ejecutar backtest
            results = backtester.run_backtest(strategy, pair_symbol, start_date, end_date)

            # Crear gráfico de equity curve
            equity_df = pd.DataFrame(results['equity_curve'])
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=equity_df['timestamp'],
                y=equity_df['equity'],
                mode='lines',
                name='Equity Curve',
                line=dict(color='blue', width=2)
            ))
            fig.update_layout(
                title=f'Backtest Results - {pair_symbol}',
                xaxis_title='Date',
                yaxis_title='Portfolio Value ($)',
                template='plotly_white'
            )
            chart_html = plot(fig, output_type='div')

            context = {
                'results': results,
                'chart': chart_html,
                'pair': pair_symbol,
                'start_date': start_date_str,
                'end_date': end_date_str,
                'initial_balance': initial_balance
            }

            messages.success(request, f"Backtest completado exitosamente. Retorno total: {results['total_return']:.2f}%")
            return render(request, 'dashboard/backtest_results.html', context)

        except Exception as e:
            messages.error(request, f"Error ejecutando backtest: {str(e)}")
            return render(request, 'dashboard/run_backtest.html')

    return render(request, 'dashboard/run_backtest.html')
