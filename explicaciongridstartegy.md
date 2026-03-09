El código actual utiliza el escaner de rango (

range_scanner
) para sugerir automáticamente los máximos y mínimos de la grilla. El criterio principal se encuentra en el archivo 

dashboard/range_finder.py
, específicamente en la función 

calculate_range_score
.

Aquí te detallo cómo lo hace y qué criterios usa:

1. ¿Qué lugar del código lo hace?
El archivo principal responsable es 

criptodash/dashboard/range_finder.py
 dentro de la función 

calculate_range_score(df, period=14)
 (específicamente entre las líneas 33 y 57).

Estos valores sugeridos luego son tomados por la vista 

range_scanner
 (en 

dashboard_views.py
) y enviados a la interfaz (

bot_dashboard.html
), donde se auto-completan en el formulario de creación del bot Grid.

2. ¿Cuáles son los criterios exactos?
El cálculo se basa en el comportamiento de las últimas 24 velas (dependiendo del timeframe que estés usando, por ejemplo, las últimas 24 horas si el timeframe es de 1h).

Los pasos que sigue el código son:

Obtener Extremos Recientes: Busca el precio más bajo (low) y el precio más alto (high) de las últimas 24 velas analizadas:

python
price_min = recent_df['low'].min()
price_max = recent_df['high'].max()
Aplicar Margen de Seguridad (0.5%): Para definir los límites exactos de la grilla, el código expande el rango un 0.5% hacia arriba y hacia abajo basándose en los extremos encontrados. Esto evita que fluctuaciones milimétricas dejen órdenes atrapadas en los bordes.

python
suggested_lower = price_min * 0.995  # 0.5% por debajo del mínimo reciente
suggested_upper = price_max * 1.005  # 0.5% por encima del máximo reciente
Redondeo inteligente según el valor de la moneda:

Si el precio es menor a $10 (ej. ADA o ATOM), lo redondea a 4 decimales.
Si el precio es mayor a $10 (ej. BTC o SOL), lo redondea a 2 decimales.
Cálculo del Stop Loss sugerido: Al mismo tiempo, calcula el punto de escape o Stop Loss poniéndolo un 2% por debajo del límite inferior sugerido (suggested_lower * 0.98).

Además de calcular estos límites, el escáner se asegura de que este rango sea "óptimo" para una estrategia de Grid, premiando (en su sistema de puntuación) variaciones que se encuentren entre el 1% y el 5% de volatilidad, acompañadas de un indicador ADX bajo (< 20-25) que confirme que el mercado está lateralizando.

Resumen: Los máximos y mínimos recomendados son simplemente los puntos más alto y más bajo de las últimas 24 velas amplificados en un 0.5% de margen.