# Plan de Implementación: Corrección de dashboard_mejorado

## Descripción del Problema

Cuando el usuario ingresa un par y fechas en `dashboard_mejorado`, la vista debería:
1. Buscar datos en la base de datos
2. Si no existen datos para ese rango de fechas, ejecutar el bot para obtenerlos
3. Mostrar el gráfico con las señales generadas

**Problemas identificados:**

1. **Error de atributo**: `data_service.py` usa `signal_strength` pero el modelo define `strength`
2. **Lógica incompleta**: Solo se ejecuta el bot si `TradingPair.DoesNotExist`, pero no cuando el par existe pero no tiene señales en el rango de fechas
3. **Falta manejo de errores**: Si el bot falla, las variables `señales` pueden quedar indefinidas
4. **Falta validación**: No se verifica si las señales están vacías después del filtrado por fechas

---

## Cambios Propuestos

### [data_service.py](file:///c:/Users/Javier/Desktop/programacion/djangoDashPub/criptodash/dashboard/data_service.py)

#### Corrección de atributo en `calcular_estadisticas_desde_señales()`

**Problema**: Línea 164 usa `s.signal_strength` pero el modelo tiene `s.strength`

**Solución**: Cambiar a `s.strength`

---

### [views.py](file:///c:/Users/Javier/Desktop/programacion/djangoDashPub/criptodash/dashboard/views.py)

#### Refactorización completa de `dashboard_mejorado()`

**Problemas actuales:**
- Solo ejecuta bot si `TradingPair.DoesNotExist`
- No verifica si hay señales después del filtrado por fechas
- Variables pueden quedar indefinidas si hay errores

**Solución**: Reestructurar la lógica:

```python
@login_required
def dashboard_mejorado(request):
    pair_symbol = request.GET.get('pair', 'ETH/USDT')
    fecha_inicio = request.GET.get('fecha_inicio')
    fecha_fin = request.GET.get('fecha_fin')
    
    # 1. Obtener o crear TradingPair
    # 2. Buscar señales en BD
    # 3. Si no hay señales, ejecutar bot
    # 4. Aplicar filtros de fecha
    # 5. Si después del filtrado no hay señales, ejecutar bot con fechas específicas
    # 6. Generar estadísticas y gráfico
    # 7. Manejar errores apropiadamente
```

---

## User Review Required

> [!WARNING]
> **Cambio en el flujo de ejecución del bot**
> 
> La nueva lógica ejecutará el bot en dos casos:
> 1. Cuando no existe el `TradingPair` en la base de datos
> 2. Cuando el par existe pero no hay señales en el rango de fechas especificado
> 
> Esto puede resultar en más llamadas a la API de Binance. ¿Es este el comportamiento deseado?

> [!IMPORTANT]
> **Formato de fecha**
> 
> El código actual espera fechas en formato `'%Y-%m-%d'` (ej: '2025-01-15'). La función `run_bot()` espera `date_from` en formato ISO 8601 (ej: '2025-01-15 00:00:00'). Necesitamos asegurar compatibilidad.

---

## Cambios Detallados

### 1. [data_service.py](file:///c:/Users/Javier/Desktop/programacion/djangoDashPub/criptodash/dashboard/data_service.py#L164)

**Línea 164**: Cambiar `signal_strength` a `strength`

```diff
-    fuerza_promedio = sum(s.signal_strength for s in señales_list) / total_señales if total_señales > 0 else 0
+    fuerza_promedio = sum(s.strength for s in señales_list) / total_señales if total_señales > 0 else 0
```

---

### 2. [views.py](file:///c:/Users/Javier/Desktop/programacion/djangoDashPub/criptodash/dashboard/views.py#L431-L500)

**Reescribir `dashboard_mejorado()`** con mejor manejo de errores y lógica:

```python
@login_required
def dashboard_mejorado(request):
    from .models import TradingPair, TradeSignal, Exchange
    from .data_service import calcular_estadisticas_desde_señales, generar_grafico_desde_señales
    from django.utils import timezone
    from datetime import datetime, timedelta
    from . import ccxttest1
    
    pair_symbol = request.GET.get('pair', 'ETH/USDT')
    fecha_inicio = request.GET.get('fecha_inicio')
    fecha_fin = request.GET.get('fecha_fin')
    
    # Inicializar variables
    señales = TradeSignal.objects.none()
    pair = None
    error_message = None
    
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
        
        # 3. Buscar señales
        señales = TradeSignal.objects.filter(pair=pair).order_by('-timestamp')
        
        # 4. Aplicar filtros de fecha
        fecha_inicio_dt = None
        fecha_fin_dt = None
        
        if fecha_inicio:
            try:
                fecha_inicio_dt = timezone.make_aware(datetime.strptime(fecha_inicio, '%Y-%m-%d'))
                señales = señales.filter(timestamp__gte=fecha_inicio_dt)
            except ValueError:
                error_message = f"Formato de fecha inicio inválido: {fecha_inicio}"
        
        if fecha_fin:
            try:
                fecha_fin_dt = timezone.make_aware(datetime.strptime(fecha_fin, '%Y-%m-%d')) + timedelta(days=1)
                señales = señales.filter(timestamp__lt=fecha_fin_dt)
            except ValueError:
                error_message = f"Formato de fecha fin inválido: {fecha_fin}"
        
        # 5. Si no hay señales, ejecutar bot
        if not señales.exists():
            try:
                # Formatear fecha para ccxt (ISO 8601)
                date_from_str = fecha_inicio + ' 00:00:00' if fecha_inicio else None
                
                # Ejecutar bot
                ccxttest1.run_bot(pair=pair_symbol, date_from=date_from_str, timeframe='1m')
                
                # Recargar señales
                señales = TradeSignal.objects.filter(pair=pair).order_by('-timestamp')
                
                # Aplicar filtros de fecha nuevamente
                if fecha_inicio_dt:
                    señales = señales.filter(timestamp__gte=fecha_inicio_dt)
                if fecha_fin_dt:
                    señales = señales.filter(timestamp__lt=fecha_fin_dt)
                    
            except Exception as e:
                error_message = f"Error al ejecutar el bot: {str(e)}"
        
    except Exception as e:
        error_message = f"Error general: {str(e)}"
    
    # 6. Calcular estadísticas y gráfico
    stats = calcular_estadisticas_desde_señales(señales)
    grafico = generar_grafico_desde_señales(señales, pair_symbol)
    
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
        'fuente_datos': 'Base de datos local',
        'error_message': error_message,
    }
    
    return render(request, 'dashboard/dashboard_mejorado.html', context)
```

---

## Plan de Verificación

### Pruebas Manuales

#### Caso 1: Par existe con datos en el rango de fechas
1. Acceder a `/nuevo/?pair=ETH/USDT&fecha_inicio=2025-11-01&fecha_fin=2025-11-30`
2. **Resultado esperado**: Muestra gráfico con señales existentes, no ejecuta bot

#### Caso 2: Par existe pero sin datos en el rango de fechas
1. Acceder a `/nuevo/?pair=ETH/USDT&fecha_inicio=2025-01-01&fecha_fin=2025-01-02`
2. **Resultado esperado**: Ejecuta bot, obtiene datos de Binance, guarda señales, muestra gráfico

#### Caso 3: Par no existe en la base de datos
1. Acceder a `/nuevo/?pair=BTC/USDT&fecha_inicio=2025-11-01`
2. **Resultado esperado**: Crea par, ejecuta bot, guarda señales, muestra gráfico

#### Caso 4: Sin fechas especificadas
1. Acceder a `/nuevo/?pair=ETH/USDT`
2. **Resultado esperado**: Muestra todas las señales del par o ejecuta bot si no hay ninguna

#### Caso 5: Fechas inválidas
1. Acceder a `/nuevo/?pair=ETH/USDT&fecha_inicio=fecha-invalida`
2. **Resultado esperado**: Muestra mensaje de error, no ejecuta bot

### Verificación de Logs

Revisar la consola de Django para confirmar:
- Mensajes de "ejecutando dashboard_mejorado"
- Mensajes de "El par no existe en la base de datos" (si aplica)
- Mensajes de "Error running the bot" (si hay errores)

### Verificación de Base de Datos

Después de ejecutar el bot, verificar en la base de datos:
```sql
SELECT COUNT(*) FROM dashboard_tradesignal WHERE pair_id = <pair_id>;
```

---

## Notas Adicionales

- El template `dashboard_mejorado.html` debería mostrar `error_message` si existe
- Considerar agregar un indicador de carga mientras el bot se ejecuta
- Evaluar agregar caché para evitar llamadas repetidas a Binance
