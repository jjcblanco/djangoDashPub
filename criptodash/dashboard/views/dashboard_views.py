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
    fecha_inicio = request.GET.get('fecha_inicio')
    fecha_fin = request.GET.get('fecha_fin')
    print(f"Par seleccionado: {pair_symbol}, Fecha inicio: {fecha_inicio}, Fecha fin: {fecha_fin}")
    
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
        
        # 3. Buscar señales
        señales = TradeSignal.objects.filter(pair=pair).order_by('-timestamp')
        
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
        print(f"Señales encontradas después del filtrado: {señales_count}, Force refresh: {force_refresh}")
        
        if señales_count == 0 or force_refresh:
            if force_refresh:
                print("Refresh solicitado, ejecutando bot...")
            else:
                print("No hay señales, ejecutando bot...")
            try:
                # Formatear fecha para ccxt (ISO 8601)
                if fecha_inicio:
                    date_from_str = fecha_inicio + ' 00:00:00'
                else:
                    # Si no hay fecha de inicio, usar una fecha reciente por defecto
                    date_from_str = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
                
                print(f"Ejecutando bot con date_from={date_from_str}")
                
                # Ejecutar bot
                ccxttest1.run_bot(pair=pair_symbol, date_from=date_from_str, timeframe='1m')
                
                print("Bot ejecutado exitosamente, recargando señales...")
                
                # Recargar señales
                señales = TradeSignal.objects.filter(pair=pair).order_by('-timestamp')
                
                # Aplicar filtros de fecha nuevamente
                if fecha_inicio_dt:
                    señales = señales.filter(timestamp__gte=fecha_inicio_dt)
                if fecha_fin_dt:
                    señales = señales.filter(timestamp__lt=fecha_fin_dt)
                
                fuente_datos = 'Binance API (recién obtenido)'
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
        grafico = generar_grafico_desde_señales(señales, pair_symbol)
    except Exception as e:
        print(f"Error al calcular estadísticas o gráfico: {e}")
        stats = {
            'total_señales': 0,
            'compras': 0,
            'ventas': 0,
            'fuerza_promedio': 0,
            'precio_promedio': 0,
            'fecha_primera_señal': None,
            'fecha_ultima_señal': None,
        }
        grafico = None
    
    # 7. Preparar contexto
    pairs = TradingPair.objects.all().order_by('symbol')
    
    context = {
        'señales': señales,
        'pairs': pairs,
        'pair_selected': pair_symbol,
        'fecha_inicio': fecha_inicio,
        'fecha_fin': fecha_fin,
        'stats': stats,
        'grafico': grafico,
        'fuente_datos': fuente_datos,
        'error_message': error_message,
    }
    
    return render(request, 'dashboard/dashboard_mejorado.html', context)
