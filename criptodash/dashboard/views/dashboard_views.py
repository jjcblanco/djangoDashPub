"""
Vistas principales del dashboard.

Este módulo contiene las vistas relacionadas con la visualización del dashboard
principal y páginas de inicio.
"""

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .utils import crear_grafico_con_señales
from ..models import TradingPair, TradeSignal, Exchange
from ..data_service import calcular_estadisticas_desde_señales, generar_grafico_desde_señales
from django.utils import timezone
from datetime import datetime, timedelta
from .. import ccxttest1
import pandas as pd


def index(request):
    """Vista de la página de inicio"""
    if not request.user.is_authenticated:
        return render(request, 'dashboard/index.html')
    return render(request, 'dashboard/index.html', {'user': request.user})


def technical_analysis(request):
    """Vista de análisis técnico"""
    context = {
        'page_title': 'Análisis Técnico Avanzado',
        'active_tab': 'technical'
    }
    return render(request, 'dashboard/index.html', context)


@login_required
def dashboard_mejorado(request):
    """
    Vista principal del dashboard mejorado con señales de trading.
    
    Muestra gráficos interactivos, estadísticas y señales de compra/venta
    para el par de trading seleccionado.
    """
    print("ejecutando dashboard_mejorado")
    pair_symbol = request.GET.get('pair', 'ETH/USDT')
    timeframe = request.GET.get('timeframe', '1h') # Sync default to 1h to match backtester
    fecha_inicio = request.GET.get('fecha_inicio')
    fecha_fin = request.GET.get('fecha_fin')
    print(f"Par seleccionado: {pair_symbol}, Timeframe: {timeframe}, Fecha inicio: {fecha_inicio}, Fecha fin: {fecha_fin}")
    
    # Inicializar variables
    señales = TradeSignal.objects.none()
    pair = None
    error_message = None
    fuente_datos = 'Base de datos local'
    
    try:
        # 1. Obtener o crear Exchange
        exchange, _ = Exchange.objects.get_or_create(name='Binance')
        
        # 2. Obtener o crear TradingPair
        pair, pair_created = TradingPair.objects.get_or_create(
            symbol=pair_symbol,
            exchange=exchange,
            defaults={
                'base_asset': pair_symbol.split('/')[0],
                'quote_asset': pair_symbol.split('/')[1] if '/' in pair_symbol else ''
            }
        )
        
        if pair_created:
            print(f"Nuevo par creado: {pair_symbol}")
        
        # 3. Buscar señales (Filtradas por timeframe)
        señales = TradeSignal.objects.filter(pair=pair, timeframe=timeframe).order_by('-timestamp')
        
        # 4. Aplicar filtros de fecha
        fecha_inicio_dt = None
        fecha_fin_dt = None
        
        if fecha_inicio:
            try:
                fecha_inicio_dt = timezone.make_aware(datetime.strptime(fecha_inicio, '%Y-%m-%d'))
                señales = señales.filter(timestamp__gte=fecha_inicio_dt)
                print(f"Filtro aplicado: fecha_inicio >= {fecha_inicio_dt}")
            except ValueError:
                error_message = f"Formato de fecha inicio inválido: {fecha_inicio}"
                print(error_message)
        
        if fecha_fin:
            try:
                # Agregar un día al fecha_fin para incluir todo el día
                fecha_fin_dt = timezone.make_aware(datetime.strptime(fecha_fin, '%Y-%m-%d')) + timedelta(days=1)
                señales = señales.filter(timestamp__lt=fecha_fin_dt)
                print(f"Filtro aplicado: fecha_fin < {fecha_fin_dt}")
            except ValueError:
                error_message = f"Formato de fecha fin inválido: {fecha_fin}"
                print(error_message)
        
        # 5. Si no hay señales O si se solicita refresh, ejecutar bot
        señales_count = señales.count()
        force_refresh = request.GET.get('refresh') == '1'
        print(f"Señales encontradas para {timeframe}: {señales_count}, Force refresh: {force_refresh}")
        
        if señales_count == 0 or force_refresh:
            if force_refresh:
                print(f"Refresh solicitado para {timeframe}, ejecutando bot...")
            else:
                print(f"No hay señales para {timeframe}, ejecutando bot...")
            try:
                # Formatear fecha para ccxt (ISO 8601)
                if fecha_inicio:
                    date_from_str = fecha_inicio + ' 00:00:00'
                else:
                    # Si no hay fecha de inicio, usar una fecha reciente por defecto
                    date_from_str = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
                
                print(f"Ejecutando bot con date_from={date_from_str}, timeframe={timeframe}")
                
                # Ejecutar bot
                ccxttest1.run_bot(pair=pair_symbol, date_from=date_from_str, timeframe=timeframe)
                
                print("Bot ejecutado exitosamente, recargando señales...")
                
                # Recargar señales
                señales = TradeSignal.objects.filter(pair=pair, timeframe=timeframe).order_by('-timestamp')
                
                # Aplicar filtros de fecha nuevamente
                if fecha_inicio_dt:
                    señales = señales.filter(timestamp__gte=fecha_inicio_dt)
                if fecha_fin_dt:
                    señales = señales.filter(timestamp__lt=fecha_fin_dt)
                
                fuente_datos = f'Binance API ({timeframe} recién obtenido)'
                print(f"Señales después de ejecutar bot: {señales.count()}")
                    
            except Exception as e:
                error_message = f"Error al ejecutar el bot: {str(e)}"
                print(error_message)
                import traceback
                traceback.print_exc()
        
    except Exception as e:
        error_message = f"Error general: {str(e)}"
        print(error_message)
        import traceback
        traceback.print_exc()
    # 6. Calcular estadísticas y gráfico
    try:
        stats = calcular_estadisticas_desde_señales(señales)
        
        # 6.5 Obtener datos OHLCV completos para el gráfico continuo
        from ..data_service import DataManager
        from ..indicadores import calculate_rsi
        
        # Obtener los datos base respetando los filtros de fecha
        # Si no hay fechas seleccionadas, limitamos a las últimas 300 velas para rendimiento
        ohlcv_df = DataManager.get_or_fetch(
            pair_symbol, 
            timeframe=timeframe, 
            start=fecha_inicio_dt, 
            end=fecha_fin_dt, 
            limit=300 if not (fecha_inicio_dt or fecha_fin_dt) else 2000
        )
        
        if not ohlcv_df.empty:
            # Calcular indicadores dinámicamente para el gráfico
            ohlcv_df['ema9'] = ohlcv_df['close'].ewm(span=9, adjust=False).mean()
            ohlcv_df['ema21'] = ohlcv_df['close'].ewm(span=21, adjust=False).mean()
            ohlcv_df['ema50'] = ohlcv_df['close'].ewm(span=50, adjust=False).mean()
            ohlcv_df['ema200'] = ohlcv_df['close'].ewm(span=200, adjust=False).mean()
            ohlcv_df['rsi'] = calculate_rsi(ohlcv_df, period=14)
            
            # Cruzar con las señales para marcarlas en el gráfico
            # Convertimos señales a DF y hacemos merge por timestamp
            if señales.exists():
                sig_df = pd.DataFrame(list(señales.values('timestamp', 'signal_type', 'price', 'strength')))
                sig_df['timestamp'] = pd.to_datetime(sig_df['timestamp'])
                # Combinar
                final_df = pd.merge(ohlcv_df, sig_df, on='timestamp', how='left')
            else:
                final_df = ohlcv_df
                
            grafico = generar_grafico_desde_señales(final_df, pair_symbol)
        else:
            # Fallback a solo señales si no hay OHLCV (raro)
            grafico = generar_grafico_desde_señales(señales, pair_symbol)
        
        # Verificar si la data está obsoleta (más de 24 horas)
        is_stale = False
        if stats['fecha_ultima_señal']:
            ahora = timezone.now()
            if ahora - stats['fecha_ultima_señal'] > timedelta(hours=24):
                is_stale = True
    except Exception as e:
        print(f"Error al calcular estadísticas o gráfico: {e}")
        import traceback
        traceback.print_exc()
        stats = {
            'total_señales': 0,
            'compras': 0,
            'ventas': 0,
            'fuerza_promedio': 0,
            'precio_promedio': 0,
            'fecha_primera_señal': None,
            'fecha_ultima_señal': None,
            'market_state': "Error",
            'grid_recommendation': "Error"
        }
        grafico = None
        is_stale = False
    
    # 7. Preparar contexto
    pairs = TradingPair.objects.all().order_by('symbol')
    
    # Obtener pares disponibles desde Binance (ya cargados en memoria)
    try:
        available_pairs = sorted([
            symbol for symbol, market in ccxttest1.binance.markets.items()
            if market.get('quote') == 'USDT'
            and market.get('spot', True)
            and market.get('active', True)
        ])
    except Exception:
        available_pairs = ['ETH/USDT', 'BTC/USDT', 'ADA/USDT', 'SOL/USDT']
    
    context = {
        'señales': señales,
        'pairs': pairs,
        'pair_selected': pair_symbol,
        'timeframe': timeframe,
        'available_pairs': available_pairs,
        'fecha_inicio': fecha_inicio,
        'fecha_fin': fecha_fin,
        'stats': stats,
        'grafico': grafico,
        'is_stale': is_stale,
        'fuente_datos': fuente_datos,
        'error_message': error_message,
    }
    
    return render(request, 'dashboard/dashboard_mejorado.html', context)
@login_required
def range_scanner(request):
    """Escanea múltiples pares de trading para encontrar mercados lateralizados."""
    from ..range_finder import calculate_range_score
    import concurrent.futures
    
    # 1. Obtener lista de pares populares a escanear
    # Por ahora escaneamos los top 15 por volumen real o seleccionados
    popular_symbols = [
        'BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'ADA/USDT', 
        'XRP/USDT', 'DOT/USDT', 'MATIC/USDT', 'LINK/USDT', 'AVA/USDT',
        'LTC/USDT', 'BCH/USDT', 'ATOM/USDT', 'ETC/USDT', 'UNI/USDT'
    ]
    
    timeframe = request.GET.get('timeframe', '1h')
    results = []

    def scan_symbol(symbol):
        try:
            bars = ccxttest1.historical_fetch_ohlcv(symbol, timeframe=timeframe, limit=100)
            if not bars: return None
            df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            score, details = calculate_range_score(df)
            return {
                'symbol': symbol,
                'score': score,
                'details': details
            }
        except Exception as e:
            print(f"Error scanning {symbol}: {e}")
            return None

    # Escaneo en paralelo (max 5 hilos para no saturar API)
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        future_to_symbol = {executor.submit(scan_symbol, s): s for s in popular_symbols}
        for future in concurrent.futures.as_completed(future_to_symbol):
            res = future.result()
            if res:
                results.append(res)
    
    # Ordenar por puntuación descendente
    results.sort(key=lambda x: x['score'], reverse=True)
    
    context = {
        'results': results,
        'timeframe': timeframe,
        'page_title': 'Escáner de Rango (Grid Finder)',
    }
    return render(request, 'dashboard/range_scanner.html', context)
@login_required
def trend_scanner(request):
    """Escanea múltiples pares de trading para encontrar tendencias alcistas o bajistas claras."""
    from ..trend_finder import calculate_trend_score
    import concurrent.futures
    import pandas as pd
    from .. import ccxttest1
    
    popular_symbols = [
        'BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'ADA/USDT', 
        'XRP/USDT', 'DOT/USDT', 'MATIC/USDT', 'LINK/USDT', 'AVAX/USDT',
        'LTC/USDT', 'BCH/USDT', 'ATOM/USDT', 'ETC/USDT', 'UNI/USDT',
        'NEAR/USDT', 'OP/USDT', 'ARB/USDT', 'INJ/USDT', 'TIA/USDT'
    ]
    
    timeframe = request.GET.get('timeframe', '1h')
    results = []

    def scan_symbol(symbol):
        try:
            bars = ccxttest1.historical_fetch_ohlcv(symbol, timeframe=timeframe, limit=250)
            if not bars: return None
            df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            score, trend_type, details = calculate_trend_score(df)
            return {
                'symbol': symbol,
                'score': score,
                'trend_type': trend_type,
                'details': details
            }
        except Exception as e:
            print(f"Error scanning {symbol}: {e}")
            return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        future_to_symbol = {executor.submit(scan_symbol, s): s for s in popular_symbols}
        for future in concurrent.futures.as_completed(future_to_symbol):
            res = future.result()
            if res:
                results.append(res)
    
    # Ordenar por puntuación descendente
    results.sort(key=lambda x: x['score'], reverse=True)
    
    context = {
        'results': results,
        'timeframe': timeframe,
        'page_title': 'Escáner de Tendencia (Trend Finder)',
    }
    return render(request, 'dashboard/trend_scanner.html', context)
