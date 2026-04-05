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
    """
    Genera un Plotly Figure multi-panel con:
    - Panel 1 (precio): Candlestick + EMAs + Ichimoku + señales buy/sell
      + S/R horizontal lines + Elliott wave annotations + Candlestick patterns
    - Panel 2 (MACD): MACD line + signal + histogram
    - Panel 3 (RSI): RSI line + overbought/oversold bands
    """
    if viz_options is None:
        viz_options = {
            'show_ema': True, 'show_rsi': True, 'show_ichimoku': False,
            'show_macd': True, 'show_sr': False,
            'show_elliott': False, 'show_patterns': False,
        }

    # --- Determine active panels ---
    show_rsi  = viz_options.get('show_rsi', True)
    show_macd = viz_options.get('show_macd', True)

    # Detect empty / queryset input
    is_empty = False
    try:
        if señales is None:
            is_empty = True
        elif hasattr(señales, 'empty'):
            is_empty = señales.empty
        elif not señales:
            is_empty = True
    except Exception:
        is_empty = False

    if is_empty:
        fig = go.Figure()
        fig.update_layout(title=f"No hay señales para {pair_symbol}", template='plotly_dark')
        return fig.to_html(full_html=False, include_plotlyjs='cdn')

    # --- Convert to DataFrame ---
    try:
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

    if 'timestamp' in df.columns:
        df['timestamp'] = pd.to_datetime(df['timestamp'])

    has_ohlc = {'open', 'high', 'low', 'close'}.issubset(df.columns)
    show_rsi  = show_rsi  and has_ohlc and 'rsi'  in df.columns and not df['rsi'].isnull().all()
    show_macd = show_macd and has_ohlc and 'macd' in df.columns and not df['macd'].isnull().all()

    # --- Build subplot grid ---
    rows = 1 + int(show_macd) + int(show_rsi)
    row_heights = {
        1: [1.0],
        2: [0.65, 0.35],
        3: [0.55, 0.25, 0.20],
    }[rows]

    subplot_titles = [f"Precio — {pair_symbol}"]
    if show_macd: subplot_titles.append("MACD")
    if show_rsi:  subplot_titles.append("RSI (14)")

    fig = make_subplots(
        rows=rows, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.04,
        row_heights=row_heights,
        subplot_titles=subplot_titles
    )

    # --- Panel 1: Candlestick ---
    if has_ohlc:
        fig.add_trace(go.Candlestick(
            x=df['timestamp'], open=df['open'], high=df['high'],
            low=df['low'], close=df['close'],
            name='Precio',
            increasing_line_color='#26a69a',
            decreasing_line_color='#ef5350',
        ), row=1, col=1)

    # --- EMAs ---
    if viz_options.get('show_ema', True):
        ema_styles = {
            'ema9':   ('rgba(100,181,246,0.9)', 1),
            'ema21':  ('rgba(255,167,38,0.9)',  1),
            'ema50':  ('rgba(239,83,80,0.9)',   1.5),
            'ema200': ('rgba(171,71,188,0.9)',  2),
        }
        for col, (color, width) in ema_styles.items():
            if col in df.columns:
                fig.add_trace(go.Scatter(
                    x=df['timestamp'], y=df[col],
                    mode='lines', name=col.upper(),
                    line=dict(color=color, width=width)
                ), row=1, col=1)

    # --- Ichimoku ---
    if viz_options.get('show_ichimoku', False) and 'senkou_a' in df.columns:
        fig.add_trace(go.Scatter(
            x=df['timestamp'], y=df['senkou_a'], mode='lines',
            line=dict(width=0), showlegend=False, name='Senkou A'
        ), row=1, col=1)
        fig.add_trace(go.Scatter(
            x=df['timestamp'], y=df['senkou_b'], mode='lines',
            line=dict(width=0), fill='tonexty',
            fillcolor='rgba(0,255,0,0.08)', name='Ichimoku Cloud'
        ), row=1, col=1)
        for line_col, color, name in [('tenkan', '#00bcd4', 'Tenkan'), ('kijun', '#ffd54f', 'Kijun')]:
            if line_col in df.columns:
                fig.add_trace(go.Scatter(
                    x=df['timestamp'], y=df[line_col], mode='lines',
                    name=name, line=dict(color=color, width=1)
                ), row=1, col=1)

    # --- Bollinger Bands ---
    if viz_options.get('show_bb', False) and 'bb_upper' in df.columns:
        for band_col, color in [('bb_upper', 'rgba(156,39,176,0.7)'), ('bb_lower', 'rgba(156,39,176,0.7)')]:
            fig.add_trace(go.Scatter(
                x=df['timestamp'], y=df[band_col], mode='lines',
                line=dict(color=color, width=1, dash='dot'),
                name=band_col.replace('_', ' ').title(), showlegend=True
            ), row=1, col=1)
        if 'bb_middle' in df.columns:
            fig.add_trace(go.Scatter(
                x=df['timestamp'], y=df['bb_middle'], mode='lines',
                line=dict(color='rgba(121,85,72,0.8)', width=1, dash='dash'),
                name='BB Middle'
            ), row=1, col=1)

    # --- Buy / Sell Signals ---
    signal_col = 'signal_type' if 'signal_type' in df.columns else None
    price_col  = 'price' if 'price' in df.columns else ('close' if 'close' in df.columns else None)
    if signal_col and price_col:
        buys  = df[df[signal_col].str.lower() == 'buy']
        sells = df[df[signal_col].str.lower() == 'sell']
        if not buys.empty:
            fig.add_trace(go.Scatter(
                x=buys['timestamp'], y=buys[price_col], mode='markers+text',
                marker=dict(color='#00e676', symbol='triangle-up', size=14,
                            line=dict(width=1, color='white')),
                text=['BUY'] * len(buys), textposition='top center',
                textfont=dict(size=9, color='#00e676'), name='Compra'
            ), row=1, col=1)
        if not sells.empty:
            fig.add_trace(go.Scatter(
                x=sells['timestamp'], y=sells[price_col], mode='markers+text',
                marker=dict(color='#ff1744', symbol='triangle-down', size=14,
                            line=dict(width=1, color='white')),
                text=['SELL'] * len(sells), textposition='bottom center',
                textfont=dict(size=9, color='#ff1744'), name='Venta'
            ), row=1, col=1)

    # --- Support & Resistance ---
    if viz_options.get('show_sr', False) and has_ohlc:
        try:
            from .indicadores import detect_support_resistance
            sr = detect_support_resistance(df)
            ts_min, ts_max = df['timestamp'].min(), df['timestamp'].max()
            for lvl in sr.get('supports', []):
                fig.add_shape(type='line', x0=ts_min, x1=ts_max, y0=lvl, y1=lvl,
                              line=dict(color='rgba(0,230,118,0.6)', width=1.5, dash='dot'),
                              row=1, col=1)
                fig.add_annotation(x=ts_max, y=lvl, text=f'S ${lvl:.2f}',
                                   showarrow=False, font=dict(color='#00e676', size=9),
                                   xanchor='right', bgcolor='rgba(0,0,0,0.4)', row=1, col=1)
            for lvl in sr.get('resistances', []):
                fig.add_shape(type='line', x0=ts_min, x1=ts_max, y0=lvl, y1=lvl,
                              line=dict(color='rgba(255,82,82,0.6)', width=1.5, dash='dot'),
                              row=1, col=1)
                fig.add_annotation(x=ts_max, y=lvl, text=f'R ${lvl:.2f}',
                                   showarrow=False, font=dict(color='#ff5252', size=9),
                                   xanchor='right', bgcolor='rgba(0,0,0,0.4)', row=1, col=1)
        except Exception as e:
            logger.warning(f"S/R detection error: {e}")

    # --- Elliott Waves ---
    if viz_options.get('show_elliott', False) and has_ohlc:
        try:
            from .indicadores import detect_elliott_waves
            waves = detect_elliott_waves(df)
            color_map = {'W1': '#fff176', 'W3': '#fff176', 'W5': '#fff176',
                         'W2': '#ef9a9a', 'W4': '#ef9a9a',
                         'A': '#f48fb1', 'B': '#80cbc4', 'C': '#f48fb1'}
            if waves:
                wts = [w['timestamp'] for w in waves]
                wps = [w['price']     for w in waves]
                wls = [w['label']     for w in waves]
                fig.add_trace(go.Scatter(
                    x=wts, y=wps, mode='lines+markers+text',
                    line=dict(color='rgba(255,241,118,0.5)', width=1.5, dash='dashdot'),
                    marker=dict(size=8, color=[color_map.get(l, '#ffffff') for l in wls]),
                    text=wls, textposition='top center',
                    textfont=dict(size=11, color='#ffe082'),
                    name='Elliott Waves'
                ), row=1, col=1)
        except Exception as e:
            logger.warning(f"Elliott detection error: {e}")

    # --- Candlestick Pattern Markers ---
    if viz_options.get('show_patterns', False) and has_ohlc:
        try:
            from .indicadores import detect_candlestick_patterns
            pdf = detect_candlestick_patterns(df.copy())
            pattern_defs = [
                ('is_hammer',          'H',  '#69f0ae', 'bottom center'),
                ('is_shooting_star',   'SS', '#ff5252', 'top center'),
                ('is_bullish_engulfing','BE', '#00e676', 'bottom center'),
                ('is_bearish_engulfing','BE', '#ff1744', 'top center'),
            ]
            for pat_col, symbol, color, pos in pattern_defs:
                if pat_col in pdf.columns:
                    pat_rows = pdf[pdf[pat_col] == True]
                    if not pat_rows.empty:
                        price_y = pat_rows['low'] if 'bottom' in pos else pat_rows['high']
                        fig.add_trace(go.Scatter(
                            x=pat_rows['timestamp'], y=price_y,
                            mode='markers+text',
                            marker=dict(symbol='circle', size=10, color=color,
                                        line=dict(width=1, color='white')),
                            text=[symbol] * len(pat_rows), textposition=pos,
                            textfont=dict(size=8, color=color),
                            name=pat_col.replace('is_', '').replace('_', ' ').title()
                        ), row=1, col=1)
        except Exception as e:
            logger.warning(f"Candlestick pattern error: {e}")

    # --- Panel MACD ---
    macd_row = 2 if show_macd else None
    if show_macd and macd_row:
        colors_hist = ['#26a69a' if v >= 0 else '#ef5350'
                       for v in df['macd_hist'].fillna(0)]
        fig.add_trace(go.Bar(
            x=df['timestamp'], y=df['macd_hist'],
            marker_color=colors_hist, name='MACD Hist', opacity=0.7
        ), row=macd_row, col=1)
        fig.add_trace(go.Scatter(
            x=df['timestamp'], y=df['macd'],
            mode='lines', name='MACD',
            line=dict(color='#42a5f5', width=1.5)
        ), row=macd_row, col=1)
        if 'signal_macd' in df.columns:
            fig.add_trace(go.Scatter(
                x=df['timestamp'], y=df['signal_macd'],
                mode='lines', name='MACD Signal',
                line=dict(color='#ff7043', width=1.5)
            ), row=macd_row, col=1)
        fig.add_shape(type='line',
                      x0=df['timestamp'].min(), x1=df['timestamp'].max(), y0=0, y1=0,
                      line=dict(color='rgba(255,255,255,0.3)', width=1),
                      row=macd_row, col=1)
        fig.update_yaxes(title_text='MACD', row=macd_row, col=1)

    # --- Panel RSI ---
    rsi_row = rows if show_rsi else None
    if show_rsi and rsi_row:
        fig.add_trace(go.Scatter(
            x=df['timestamp'], y=df['rsi'],
            mode='lines', name='RSI 14',
            line=dict(color='#ffd54f', width=1.5),
            fill='tozeroy', fillcolor='rgba(255,213,79,0.05)'
        ), row=rsi_row, col=1)
        for level, color in [(70, 'rgba(239,83,80,0.6)'), (30, 'rgba(38,166,154,0.6)'), (50, 'rgba(255,255,255,0.2)')]:
            fig.add_shape(type='line',
                          x0=df['timestamp'].min(), x1=df['timestamp'].max(), y0=level, y1=level,
                          line=dict(color=color, width=1, dash='dash'),
                          row=rsi_row, col=1)
        fig.update_yaxes(title_text='RSI', range=[0, 100], row=rsi_row, col=1)

    # --- Layout ---
    fig.update_layout(
        title=dict(text=f"📊 {pair_symbol} — Análisis Avanzado", font=dict(size=16)),
        template='plotly_dark',
        height=800 + 150 * (rows - 1),
        xaxis_rangeslider_visible=False,
        hovermode='x unified',
        legend=dict(orientation='h', yanchor='bottom', y=1.01, xanchor='right', x=1, font=dict(size=10)),
        margin=dict(l=50, r=60, t=70, b=30),
        paper_bgcolor='#1a1a2e',
        plot_bgcolor='#16213e',
    )
    fig.update_yaxes(title_text='Precio (USDT)', row=1, col=1, gridcolor='rgba(255,255,255,0.05)')
    fig.update_xaxes(gridcolor='rgba(255,255,255,0.05)', showspikes=True, spikemode='across')

    return fig.to_html(full_html=False, include_plotlyjs='cdn')


