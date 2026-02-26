Walkthrough: Grid Trading & Day Trading Implementation
Este documento resume las nuevas capacidades añadidas al sistema de backtesting, enfocándose en la estrategia de Grid Trading y las mejoras previas de Day Trading.

[NUEVO] Estrategia de Grid Trading (Malla)
He implementado una estrategia de Grid Trading avanzada con gestión de riesgo integrada. A diferencia de las estrategias lineales, esta permite mantener múltiples posiciones abiertas simultáneamente en diferentes niveles de precio.

Características Clave
Motor de Simulación Especializado: Se ha desarrollado 
simulate_grid_trading
 dentro del 
Backtester
 para manejar carteras de órdenes.
Malla Aritmética: Crea niveles de compra/venta a intervalos regulares entre un precio superior e inferior definido por el usuario.
Gestión de Riesgo (Global Stop Loss): El sistema detecta si el precio sale del rango de la malla por la parte inferior y, si toca el precio de seguridad, cierra todas las posiciones abiertas y detiene la estrategia para proteger el capital.
Toma de Ganancias por Nivel: Cada compra en un nivel de la malla tiene su propio objetivo de venta en el nivel superior inmediatamente siguiente.
IMPORTANT

Simulación Realista: El motor calcula la curva de equidad (Equity Curve) sumando el balance disponible más el valor de mercado actual de todas las posiciones abiertas en cada segundo del backtest.

Day Trading (EMA Ribbon Scalper)
Continuamos mejorando la estrategia de Day Trading para temporalidades de 5m o 15m.

Filtro de Velas Japonesas
Para maximizar la precisión, la estrategia busca confirmaciones físicas:

Compras: Martillo (Hammer) o Envolvente Alcista.
Ventas: Estrella Fugaz o Envolvente Bajista.
Mejoras en la Interfaz y Backend
UI Inteligente: El formulario de backtest ahora es dinámico. Al seleccionar "Grid Trading", la interfaz oculta los filtros estándar de indicadores y muestra los parámetros específicos del Grid (Rango, Niveles, Monto por Nivel).
Motor Modular: La clase 
Backtester
 ahora ramifica su ejecución automáticamente según la estrategia seleccionada, permitiendo comparar una estrategia de "comprar y mantener" con una de malla en el mismo entorno.
Estadísticas Detalladas: Los resultados ahora incluyen el desglose de trades, PnL por operación y la visualización de la curva de equidad.
Verificación del Grid Trading
Se realizó una prueba técnica (
test_grid_strategy.py
) con los siguientes resultados:

Mercado Lateral: La estrategia generó múltiples compras y ventas exitosas ("scalping" de malla), acumulando ganancias pequeñas pero constantes.
Ruptura Bajista: Al simular una caída fuerte fuera del rango, el Global Stop Loss se activó correctamente a $82.0, liquidando las posiciones y evitando que el balance siguiera cayendo mientras el precio llegaba a $75.0.
TIP

Para obtener los mejores resultados con el Grid, buscá pares que se encuentren en un canal lateral amplio. Definí el rango superior e inferior basándote en soportes y resistencias históricas de los últimos 30 días.
