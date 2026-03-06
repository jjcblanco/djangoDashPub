from decimal import Decimal
import pandas as pd
import logging
from django.db import transaction
from plotly import graph_objs as go
from django.utils import timezone
from .models import OHLCVData, TradingPair, Exchange
from .ccxttest1 import historical_fetch_ohlcv  # Tu función actual

logger = logging.getLogger(__name__)

class DataManager:
    @staticmethod
    def _normalize_ts(ts):
        """Normaliza timestamp a datetime (acepta ms int, str ISO, datetime)."""
        from datetime import datetime
        if ts is None:
            return None
        if isinstance(ts, int) or isinstance(ts, float):
            # asume ms
            try:
                return datetime.fromtimestamp(int(ts) / 1000.0)
            except Exception:
                return datetime.fromtimestamp(int(ts))
        if isinstance(ts, str):
            try:
                return pd.to_datetime(ts).to_pydatetime()
            except Exception:
                return None
        if hasattr(ts, 'year'):
            return ts
        return None

    @staticmethod
    def fetch_ohlcv_from_exchange(pair_symbol, timeframe='1m', since=None, limit=1000):
        """
        Llama historical_fetch_ohlcv y devuelve DataFrame con columnas:
        ['timestamp','open','high','low','close','volume']
        """
        raw = historical_fetch_ohlcv(pair_symbol, timeframe=timeframe, since=since, limit=limit)
        if not raw:
            return pd.DataFrame(columns=['timestamp','open','high','low','close','volume'])
        # raw puede ser lista de listas: [ts, open, high, low, close, volume]
        rows = []
        for row in raw:
            try:
                ts = DataManager._normalize_ts(row[0])
                rows.append({
                    'timestamp': ts,
                    'open': float(row[1]),
                    'high': float(row[2]),
                    'low': float(row[3]),
                    'close': float(row[4]),
                    'volume': float(row[5]) if len(row) > 5 else 0.0
                })
            except Exception:
                continue
        df = pd.DataFrame(rows)
        if not df.empty:
            df = df.sort_values('timestamp').reset_index(drop=True)
        return df

    @staticmethod
    def get_ohlcv_from_db(pair_obj, timeframe='1m', start=None, end=None):
        """
        Recupera OHLCVData desde la BD y devuelve DataFrame.
        pair_obj: TradingPair instance
        """
        qs = OHLCVData.objects.filter(pair=pair_obj, timeframe=timeframe).order_by('timestamp')
        if start:
            qs = qs.filter(timestamp__gte=start)
        if end:
            qs = qs.filter(timestamp__lte=end)
        if not qs.exists():
            return pd.DataFrame(columns=['timestamp','open','high','low','close','volume'])
        df = pd.DataFrame(list(qs.values('timestamp','open','high','low','close','volume')))
        if not df.empty:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.sort_values('timestamp').reset_index(drop=True)
        return df

    @staticmethod
    def save_ohlcv_rows(df, pair_obj, timeframe='1m', batch_size=500):
        """
        Guarda (bulk_create) filas del DataFrame en OHLCVData.
        Evita duplicados mediante ignore_conflicts cuando está disponible.
        """
        if df is None or df.empty:
            return 0
        objs = []
        for _, r in df.iterrows():
            try:
                objs.append(OHLCVData(
                    pair=pair_obj,
                    timestamp=r['timestamp'],
                    open=Decimal(str(r['open'])),
                    high=Decimal(str(r['high'])),
                    low=Decimal(str(r['low'])),
                    close=Decimal(str(r['close'])),
                    volume=Decimal(str(r.get('volume', 0))),
                    timeframe=timeframe
                ))
            except Exception as e:
                logger.debug("skip row save_ohlcv_rows: %s", e)
        created = 0
        try:
            with transaction.atomic():
                OHLCVData.objects.bulk_create(objs, batch_size=batch_size, ignore_conflicts=True)
                created = len(objs)
        except TypeError:
            # ignore_conflicts no disponible en versiones antiguas -> insert en loop
            for o in objs:
                try:
                    o.save()
                    created += 1
                except Exception:
                    continue
        except Exception as e:
            logger.exception("Error saving OHLCV rows: %s", e)
        return created

    @staticmethod
    def get_or_fetch(pair_symbol, timeframe='1m', start=None, end=None, limit=1000):
        """
        Intenta obtener datos de la BD; si insuficientes, consulta exchange y guarda.
        Devuelve DataFrame con ohlcv.
        """
        try:
            pair_obj = TradingPair.objects.get(symbol=pair_symbol)
        except TradingPair.DoesNotExist:
            # no existe el par en BD -> fetch pero no guardar
            return DataManager.fetch_ohlcv_from_exchange(pair_symbol, timeframe, since=start, limit=limit)
        df_db = DataManager.get_ohlcv_from_db(pair_obj, timeframe, start=start, end=end)
        # Si no hay datos en DB o rango insuficiente, fetch desde exchange
        if df_db.empty:
            df_ext = DataManager.fetch_ohlcv_from_exchange(pair_symbol, timeframe, since=start, limit=limit)
            if not df_ext.empty:
                DataManager.save_ohlcv_rows(df_ext, pair_obj, timeframe=timeframe)
            return df_ext
        return df_db


def calcular_estadisticas_desde_señales(señales):
    """Calcula estadísticas desde las señales de trading"""
    if not señales:
        return {
            'total_señales': 0,
            'compras': 0,
            'ventas': 0,
            'fuerza_promedio': 0,
            'precio_promedio': 0,
            'fecha_primera_señal': None,
            'fecha_ultima_señal': None,
        }

    señales_list = list(señales)

    # Calcular estadísticas básicas
    total_señales = len(señales_list)
    compras = len([s for s in señales_list if s.signal_type == 'buy'])
    ventas = len([s for s in señales_list if s.signal_type == 'sell'])

    # Fuerza promedio
    fuerza_promedio = sum(s.strength for s in señales_list) / total_señales if total_señales > 0 else 0

    # Precio promedio
    precio_promedio = sum(s.price for s in señales_list) / total_señales if total_señales > 0 else 0

    # Fechas
    fechas = [s.timestamp for s in señales_list]
    fecha_primera = min(fechas) if fechas else None
    fecha_ultima = max(fechas) if fechas else None

    # Calcular Estado del Mercado (Lateralización)
    # Basado en el ADX promedio de las señales que lo tengan
    adx_values = [s.indicators.get('adx') for s in señales_list if s.indicators and s.indicators.get('adx')]
    avg_adx = sum(adx_values) / len(adx_values) if adx_values else 0
    
    # Lógica de lateralización
    if not adx_values:
        market_state = "Indeterminado"
        grid_recommendation = "N/A"
    elif avg_adx < 20:
        market_state = "Ranging (Lateral)"
        grid_recommendation = "¡Muy conveniente!"
    elif avg_adx < 25:
        market_state = "Consolidación"
        grid_recommendation = "Conveniente"
    else:
        market_state = "Trending (Tendencia)"
        grid_recommendation = "Evitar Grid"

    return {
        'total_señales': total_señales,
        'compras': compras,
        'ventas': ventas,
        'fuerza_promedio': round(fuerza_promedio, 2),
        'precio_promedio': round(precio_promedio, 4),
        'fecha_primera_señal': fecha_primera,
        'fecha_ultima_señal': fecha_ultima,
        'avg_adx': round(avg_adx, 1),
        'market_state': market_state,
        'grid_recommendation': grid_recommendation,
    }


from plotly.subplots import make_subplots

def generar_grafico_desde_señales(señales, pair_symbol='ETH/USDT', viz_options=None):
    """Genera y devuelve un plotly.graph_objs.Figure a partir de señales"""
    if viz_options is None:
        viz_options = {'show_ema': True, 'show_rsi': True, 'show_ichimoku': False}
        
    # Evitar error de ambigüedad con DataFrames
    is_empty = False
    try:
        if señales is None:
            is_empty = True
        elif hasattr(señales, 'empty'):
            is_empty = señales.empty
        elif not señales:
            is_empty = True
    except Exception:
        # Si hay ambigüedad o error, asumimos que NO está vacío para intentar procesarlo
        is_empty = False
        
    if is_empty:
        # devolver figura vacía
        fig = go.Figure()
        fig.update_layout(title=f"No hay señales para {pair_symbol}", template='plotly_dark')
        return fig.to_html(full_html=False, include_plotlyjs='cdn')

    # si 'señales' es queryset -> convertir a DataFrame
    try:
        import pandas as pd
        if hasattr(señales, 'values'):
            df = pd.DataFrame(list(señales.values()))
        else:
            df = pd.DataFrame(señales)
    except Exception:
        df = pd.DataFrame(señales)

    if df.empty:
        fig = go.Figure()
        fig.update_layout(title=f"No hay señales para {pair_symbol}")
        return fig.to_html(full_html=False, include_plotlyjs='cdn')

    # asegurarse de columnas timestamp/open/high/low/close/volume si existen
    if 'timestamp' in df.columns:
        df['timestamp'] = pd.to_datetime(df['timestamp'])

    # Crear subplots: Fila 1 para precio, Fila 2 para RSI
    show_rsi = viz_options.get('show_rsi', True) and 'rsi' in df.columns and not df['rsi'].isnull().all()
    
    if show_rsi:
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                            vertical_spacing=0.05, 
                            row_heights=[0.7, 0.3])
    else:
        fig = go.Figure()

    # Trace 1: Candlestick
    if {'open','high','low','close'}.issubset(df.columns):
        fig.add_trace(go.Candlestick(
            x=df['timestamp'], open=df['open'], high=df['high'],
            low=df['low'], close=df['close'], name='Candlestick'
        ), row=1, col=1 if show_rsi else None)

    # Añadir EMAs si existen y están activas
    if viz_options.get('show_ema', True):
        ema_colors = {'ema9': 'blue', 'ema21': 'orange', 'ema50': 'red', 'ema200': 'purple'}
        for ema_col, color in ema_colors.items():
            if ema_col in df.columns:
                fig.add_trace(go.Scatter(
                    x=df['timestamp'], y=df[ema_col], 
                    mode='lines', name=ema_col.upper(),
                    line=dict(color=color, width=1)
                ), row=1, col=1 if show_rsi else None)

    # Añadir Ichimoku si existe y está activo
    if viz_options.get('show_ichimoku', False) and 'senkou_a' in df.columns:
        # Nube (Kumo)
        fig.add_trace(go.Scatter(
            x=df['timestamp'], y=df['senkou_a'],
            mode='lines', line=dict(width=0),
            showlegend=False, name='Senkou A'
        ), row=1, col=1 if show_rsi else None)
        
        fig.add_trace(go.Scatter(
            x=df['timestamp'], y=df['senkou_b'],
            mode='lines', line=dict(width=0),
            fill='tonexty', fillcolor='rgba(0, 255, 0, 0.1)',
            name='Ichimoku Cloud'
        ), row=1, col=1 if show_rsi else None)
        
        # Tenkan y Kijun
        if 'tenkan' in df.columns:
            fig.add_trace(go.Scatter(x=df['timestamp'], y=df['tenkan'], mode='lines', name='Tenkan', line=dict(color='cyan', width=1)), row=1, col=1 if show_rsi else None)
        if 'kijun' in df.columns:
            fig.add_trace(go.Scatter(x=df['timestamp'], y=df['kijun'], mode='lines', name='Kijun', line=dict(color='yellow', width=1)), row=1, col=1 if show_rsi else None)

    # añadir señales buy/sell si existen
    if 'signal_type' in df.columns:
        buys = df[df['signal_type'].str.lower() == 'buy']
        sells = df[df['signal_type'].str.lower() == 'sell']
        if not buys.empty:
            fig.add_trace(go.Scatter(x=buys['timestamp'], y=buys.get('price', buys.get('close')), mode='markers',
                                     marker=dict(color='green', symbol='triangle-up', size=12), name='Buy'),
                          row=1, col=1 if show_rsi else None)
        if not sells.empty:
            fig.add_trace(go.Scatter(x=sells['timestamp'], y=sells.get('price', sells.get('close')), mode='markers',
                                     marker=dict(color='red', symbol='triangle-down', size=12), name='Sell'),
                          row=1, col=1 if show_rsi else None)

    # Panel RSI
    if show_rsi:
        fig.add_trace(go.Scatter(
            x=df['timestamp'], y=df['rsi'], 
            mode='lines', name='RSI',
            line=dict(color='yellow', width=1.5)
        ), row=2, col=1)
        
        # Líneas de sobrecompra/sobreventa
        fig.add_shape(type="line", x0=df['timestamp'].min(), y0=70, x1=df['timestamp'].max(), y1=70,
                      line=dict(color="red", width=1, dash="dash"), row=2, col=1)
        fig.add_shape(type="line", x0=df['timestamp'].min(), y0=30, x1=df['timestamp'].max(), y1=30,
                      line=dict(color="green", width=1, dash="dash"), row=2, col=1)
        
        fig.update_yaxes(title_text="RSI", range=[0, 100], row=2, col=1)

    fig.update_layout(
        title=f"Gráfico Avanzado - {pair_symbol}",
        xaxis_title='Fecha/Hora',
        yaxis_title='Precio',
        template='plotly_dark',
        height=800,
        xaxis_rangeslider_visible=False
    )
    
    # Convertir a HTML para renderizar en el template
    return fig.to_html(full_html=False, include_plotlyjs='cdn')
