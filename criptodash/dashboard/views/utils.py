"""
Funciones auxiliares compartidas para las vistas del dashboard.

Este módulo contiene funciones de utilidad que son usadas por múltiples vistas,
como generación de gráficos y cálculo de estadísticas.
"""

import logging
import pandas as pd
import plotly.graph_objects as go
from functools import wraps
from django.core.cache import cache
from django.http import JsonResponse

logger = logging.getLogger(__name__)


def ajax_rate_limit(max_calls=30, period_seconds=60):
    """
    Decorador de rate limiting para endpoints AJAX usando Django Cache.
    No requiere dependencias extra (usa el cache backend ya configurado).

    Uso:
        @login_required
        @ajax_rate_limit(max_calls=10, period_seconds=60)
        def mi_endpoint(request):
            ...

    Si se excede el límite, devuelve HTTP 429 con JSON de error.
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Identificar al usuario (autenticado) o por IP (anónimo)
            user_id = request.user.id if request.user.is_authenticated else request.META.get('REMOTE_ADDR', 'anon')
            view_name = view_func.__name__
            cache_key = f"rl:{view_name}:{user_id}"

            # Obtener o inicializar el contador
            call_data = cache.get(cache_key)
            if call_data is None:
                cache.set(cache_key, {'count': 1, 'reset_at': period_seconds}, period_seconds)
            else:
                count = call_data['count'] + 1
                if count > max_calls:
                    logger.warning(
                        f"[RateLimit] Usuario {user_id} excedió el límite en '{view_name}' "
                        f"({count}/{max_calls} en {period_seconds}s)"
                    )
                    return JsonResponse({
                        'error': 'Too Many Requests',
                        'message': f'Límite de {max_calls} peticiones por {period_seconds}s superado. Intentá de nuevo en {period_seconds}s.',
                        'retry_after': period_seconds,
                    }, status=429)
                cache.set(cache_key, {'count': count}, timeout=None)  # mantiene el TTL original

            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


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
