
Planning updates and recommendations...
Created 8 todos

Empiezo con un plan corto y luego las recomendaciones concretas y cambios propuestos.

Plan (siguientes pasos)

Revisar los modelos y el punto donde se guardan las señales.
Diseñar un modelo Pair y actualizar TradingSignal para relacionar señales con pares y tipos.
Modificar la ingesta (función del bot) para etiquetar cada registro con pair y pair_type.
Añadir selector de par en los templates y endpoints para filtrar por par.
Preparar migraciones y script de backfill para datos existentes.
Añadir recomendaciones de performance (índices, particionado, caché, tareas en background).
Sigue una propuesta técnica y precisa —incluye cambios de esquema, ejemplos de código y migraciones— para que puedas indicarme si procedo a implementarlos automáticamente.

Análisis de la necesidad

Actualmente las señales y el dashboard mezclan datos de todos los pares; quieres analizar por separado distintos tipos de pares (por ejemplo: spot vs futures, o grupos de pares como ETH/USDT, BTC/USDT, etc.).
Necesitamos tratar el par como primera clase: modelo dedicado, campo en señales, filtros en vistas y API, y optimizaciones DB para consultas por par.
Cambios recomendados (prioridad alta → baja)

Cambios en modelos (imprescindible)
Añadir modelo Pair (tabla pairs) con campos:
symbol (varchar, único) — ej. "ETH/USDT"
base_asset, quote_asset
pair_type (enum/string) — e.g. "spot", "futures", "perp"
exchange (opcional)
tick_size, min_notional (opcional para normalización)
índices en symbol y (pair_type, symbol)
Actualizar TradingSignal para:
reemplazar campos de texto de par por FK hacia Pair (pair = models.ForeignKey(Pair, on_delete=...))
añadir índice compuesto en (pair_id, timestamp) para consultas rápidas por rango de tiempo y par
añadir campo source/origin si no existe (indica api, bot, manual)
Ejemplo (Django models.py snippet):
Provide snippet in answer.
Ingesta / normalización de datos (bot)
Asegurar que ccxttest1.run_bot devuelve el pair o que el wrapper que persiste señales (por ejemplo actualizar_bd_con_señales) añade la referencia: buscar/crear Pair por symbol y asignar pair_id.
Normalizar timestamps y timezone (UTC) y crear pruebas unitarias.
Si el bot devuelve distintos formatos según exchange, centralizar en una función normalize_bot_output(result, symbol).
Vistas y plantillas (frontend)
Agregar selector de pares en dashboard/index.html y en dashboard_mejorado.html (ya añadiste pair en views; estandariza).
Cambiar endpoints para aceptar ?pair=ETH/USDT y para mostrar solo señales de ese par.
Añadir página de administración para Pair (registro de pares permitidos) en dashboard/admin.py.
API endpoints
Añadir rutas JSON:
/api/pairs/ — lista pares y metadatos
/api/signals/?pair=ETH/USDT&from=...&to=...&type=buy — señales filtradas
/api/run-analysis/?pair=ETH/USDT — disparar análisis por par (enqueue job)
Documentación OpenAPI simple o endpoints en README.
Migrations y backfill
Crear migrations para nuevo modelo y cambios a TradingSignal.
Script backfill_pairs.py:
Para señales existentes que usan symbol string, agrupar por valor y crear Pair entries, asociar señales.
Ejecutar en entorno de staging antes de producción.
Performance y escalabilidad
Índices: CREATE INDEX ix_signals_pair_timestamp ON dashboard_tradingsignal(pair_id, timestamp);
Considerar particionado por pair o rango de timestamp para tablas grandes (MySQL partitioning by LIST or RANGE).
Considerar cache para datos agregados por pair (Redis).
Usar background workers (Celery + Redis/RabbitMQ) para ejecutar análisis por pair (evita bloquear request).
Monitorizar queries lentas y añadir EXPLAIN plans.
Soporte para distintos "tipos" de pair (spot/futures)
Pair.pair_type para distinguir y en vistas permitir seleccionar tipo.
En el bot, pasar parameter market_type a ccxt exchange call.
UX / reports
Permitir seleccionar múltiples pares para comparar.
Guardar "perfiles de análisis" por usuario (favorite pairs).
Export CSV/JSON por par.
Testing
Unit tests para:
creación de Pair y linking
endpoints que filtran por pair
backfill script idempotente
Opcionales avanzados
Multi-DB sharding por par (solo si escala extremo).
Data lake / timeseries DB (InfluxDB, TimescaleDB) si grandes volúmenes de ticks.
Ejemplos de código (snippets)

Provide Django model snippet: Pair and modified TradingSignal.
Provide snippet for updating ingestion/wrapper: find_or_create Pair.
Provide view update example to filter by pair.
I'll include concise code blocks in Spanish.

Model snippet:

(Will include code inline.)

Backfill script example: create pairs and update TradingSignal.

SQL index snippet.

Celery suggestion: brief example of task function signature.

Impacto en la base de datos

Nueva tabla pairs
Modificación de trading_signal (añadir FK, índice)
Migraciones generadas + backfill
Downtime: small window recommended when running migrations that alter columns—can do in steps: add nullable FK, backfill, then make non-nullable.
Plan de migración seguro (recomendado)

Add pair FK nullable to TradingSignal.
Deploy code that fills pair when creating new signals.
Run backfill script to populate for existing rows.
Add DB constraint NOT NULL if desired.
Add indices.
Siguiente paso

¿Quieres que aplique estos cambios automáticamente ahora? Puedo:
abrir dashboard/models.py and create Pair model and update TradingSignal
add admin registration
add helper function to ingestion
create migration files (apply_patch tool needed)
But must ask user because changes are invasive.
Ask user preference: implement now or just a detailed patch? Also ask whether they want background worker set up.

Conclude in Spanish and offer to implement.

We must ensure to use final message format guidelines; use bold section headers with Title Case; bullets with bold keywords. Use backticks around filenames. Provide code blocks in monospace; earlier instruction: wrap commands and file paths in backticks. Use no heavy formatting? Final answer guidelines: use Title Case headers. Good.

Let's produce final response in Spanish, include code snippets. Not call more tools.Próximo paso: voy a proponerte cambios concretos y un plan para implementarlos; dime si quieres que los aplique ahora.

Resumen corto (qué voy a proponer)

Añadir un modelo Pair y relacionarlo con las señales para poder filtrar/analizar por par y por tipo (spot/futures).
Cambiar la ingesta para que cada señal guarde pair (FK) y pair_type.
Actualizar vistas, templates y API para filtrar por pair.
Preparar migraciones + script de backfill de datos existentes.
Recomendaciones de rendimiento: índices, cache y tareas en background (Celery/RQ).
Plan (acciones que ejecutaré si autorizas)

Revisar modelos e ingesta actual.
Añadir Pair y adaptar TradingSignal (FK + índices).
Actualizar la función que persiste señales para buscar/crear Pair.
Añadir selector de pair en templates y parámetros ?pair= en vistas/API.
Crear migration + script backfill_pairs.py.
Añadir índices y recomendaciones de particionado/caché.
Tests rápidos y documentación.
¿Procedo a implementar los cambios (crear código y migrations) ahora?

A continuación tienes los detalles técnicos y ejemplos listos para aplicar.

1) Modelo recomendado

Nuevo modelo Pair para describir cada par y su tipo.
Modificar TradingSignal para referenciar Pair y añadir índices para consultas por (pair, timestamp).
Ejemplo (añadir a dashboard/models.py o a la app que contiene TradingSignal — ajusta el import si tu TradingSignal está en trading_bot.models):

Modificar TradingSignal (ejemplo):

Notas:

Empezar con pair nullable: null=True para permitir migración gradual (add nullable FK → backfill → set NOT NULL).
on_delete=models.PROTECT evita borrar un Pair usado por señales.
2) Cambios en la ingesta (bot / persistencia)

Donde guardas señales (por ejemplo trading_bot.signals_utils.actualizar_bd_con_señales), cambia el flujo para:
obtener symbol del resultado (por ejemplo ETH/USDT)
buscar Pair.objects.get_or_create(symbol=symbol, defaults={...})
asignar pair FK a cada TradingSignal antes de crear/guardar
Ejemplo wrapper:

3) Vistas y templates

Añadir selector pair (drop-down o autocomplete) en dashboard/templates/dashboard/index.html y dashboard_mejorado.html.
Modificar vistas para leer request.GET.get('pair') y filtrar: TradingSignal.objects.filter(pair__symbol=pair_symbol, timestamp__range=(from,to)).
Mantén compatibilidad si pair no está presente (muestra todos o un default).
Ejemplo vista (simplificada):

4) API endpoints

Añadir endpoints JSON útiles:
GET /api/pairs/ → lista de pares (symbol, type, exchange)
GET /api/signals/?pair=ETH/USDT&from=...&to=...&type=buy → señales filtradas
POST /api/analysis/run/ → desencadenar análisis por pair (enqueue job)
Implementar paginación y límites.
5) Migraciones y backfill

Estrategia segura:
Crear y aplicar migration que añade Pair y añade pair FK en TradingSignal como nullable.
Desplegar código que use get_or_create cuando guarde nuevas señales.
Ejecutar backfill_pairs.py que:
agrupa señales por el campo string actual que indique pair (si existe),
crea Pair por cada símbolo,
actualiza señales antiguas signal.pair = created_pair
Añadir migration para setear pair como null=False si quieres forzar.
backfill_pairs.py ejemplo (esqueleto):
6) Índices y rendimiento

Crear índices compuestos: (pair_id, timestamp) y (pair_id, signal_type, timestamp).
Si millones de filas: considerar particionar la tabla por RANGE(timestamp) o LIST(symbol) en MySQL.
Considerar mover señales a TS DB (TimescaleDB/Postgres) si consultas por time-series son prioritarias.
Añadir Redis cache para endpoints de agregados por pair.
SQL de ejemplo para índice:

7) Background processing

Para análisis por pair (que puede tardar), usar Celery + Redis:
Endpoint POST /api/analysis/run/ encola tarea run_analysis_for_pair.delay(pair_symbol, params).
Worker ejecuta ccxttest1.run_bot(pair=pair_symbol, ...), guarda señales con pair FK.
8) UX y organización

En UI permitir:
filtro por pair_type (spot/futures)
selector de múltiples pares para comparación
guardar “favoritos” por usuario
En admin: registro central de pares autorizados (para validar inputs).
9) Tests

Tests unitarios para:
Pair creation and uniqueness
ingestion wrapper ensure_pair
views that filter by pair
backfill idempotency
10) Riesgos e impacto

Cambios en esquema requieren migraciones y backfill; seguir la estrategia migratoria para evitar downtime.
Si TradingSignal es grande, la operación UPDATE de backfill puede ser lenta; hacerlo por lotes y fuera de hora pico.
Siguientes decisiones que necesito de tu parte

¿Quieres que implemente:
A) los modelos (Pair) + vistas básicas + función ensure_pair y el script de backfill ahora (puedo aplicar cambios en el repo), o
B) solo te entregue los patches y scripts para que los revises / ejecutes tú manualmente?
¿Prefieres que las nuevas señales se creen con pair nullable inicialmente (recomendado) o quieres obligar pair desde el principio (implica downtime o inserción de valores por defecto)?
¿Quieres que también configure el worker (Celery) y Redis o lo dejamos como recomendación/documentación?
Si confirmas “implementa A”, procedo con:

editar dashboard/models.py (o trading_bot/models.py si ahí está TradingSignal),
editar ingestion wrapper para Pair (crear dashboard/utils.py con ensure_pair),
añadir admin registration de Pair,
crear templates mínimos (selector de pair),
añadir script scripts/backfill_pairs.py,
añadir migration skeletons (nota: generar migrations aquí no ejecutará python manage.py makemigrations localmente; te crearé las modificaciones de código y el script de backfill — luego tú ejecutas makemigrations y migrate).