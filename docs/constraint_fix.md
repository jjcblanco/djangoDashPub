# 🔧 Fix: MySQL Constraint Error en Campo `indicators`

## Error Original

```
Error saving signals to database: (4025, 'CONSTRAINT `dashboard_tradesignal.indicators` failed for `trading_db`.`dashboard_tradesignal`')
```

## Causa del Problema

El campo `indicators` en el modelo `TradeSignal` es un `JSONField` con `null=True, blank=True`. MySQL tiene una restricción CHECK que no permite guardar diccionarios vacíos `{}` en campos JSON.

**Código problemático**:
```python
indicators = {}  # Diccionario vacío
# ... no se agregan indicadores ...
defaults = {
    'indicators': indicators,  # Guarda {} - FALLA en MySQL
}
```

## Solución Aplicada

Cambiar el código para guardar `None` en lugar de diccionario vacío cuando no hay indicadores.

**Código corregido** en [ccxttest1.py:227-289](file:///c:/Users/Javier/Desktop/programacion/djangoDashPub/criptodash/dashboard/ccxttest1.py#L227-L289):

```python
# Prepare indicators data
indicators = {}
if 'rsi' in row and not pd.isna(row['rsi']):
    indicators['rsi'] = float(row['rsi'])
if 'in_uptrend' in row and not pd.isna(row['in_uptrend']):
    indicators['in_uptrend'] = bool(row['in_uptrend'])
if 'macd' in row and not pd.isna(row['macd']):
    indicators['macd'] = float(row['macd'])
if 'macd_signal' in row and not pd.isna(row['macd_signal']):
    indicators['macd_signal'] = float(row['macd_signal'])

defaults = {
    'price': float(row['close']),
    'strength': strength,
    # ✅ Usa None si el dict está vacío
    'indicators': indicators if indicators else None,
    'indicator': ','.join(list(indicators.keys())) if indicators else None,
}
```

## Mejoras Adicionales

1. ✅ **Validación de NaN**: Agregado `not pd.isna()` para `in_uptrend`
2. ✅ **Más indicadores**: Agregado soporte para `macd` y `macd_signal`
3. ✅ **Mejor logging**: Agregado `traceback.print_exc()` para debugging

## Resultado

Ahora el campo `indicators` se guarda como:
- `None` cuando no hay indicadores → ✅ MySQL acepta NULL
- `{"rsi": 45.2, "in_uptrend": true}` cuando hay indicadores → ✅ MySQL acepta JSON válido
- ~~`{}`~~ nunca se guarda → ❌ MySQL rechazaba esto

## Prueba

Ejecuta el dashboard nuevamente:
```
/nuevo/?pair=ETH/USDT&fecha_inicio=2025-01-01
```

El error ya no debería aparecer y las señales se guardarán correctamente.
