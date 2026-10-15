# Informe de Análisis del Sistema — CriptoDash

Fecha: 2026-10-13 · Alcance: código completo (~28k líneas Python), infraestructura VPS, migraciones y repositorio.

---

## 1. Resumen ejecutivo

El código de negocio (ORM, tareas Celery, vistas principales) está razonablemente escrito, pero el sistema tiene **5 agujeros serios** que requieren acción:

1. **Credenciales reales en un repo público de GitHub** (OAuth de Google, password MySQL).
2. **DEBUG=True y ALLOWED_HOSTS=*** como estado efectivo de configuración (el `.env` real lo tiene).
3. **Migraciones con drift**: índice declarado nunca migrado, SQL aplicado a mano en producción, diamante `0002` operativamente ambiguo.
4. **Tres productores concurrentes de sync de ballenas sin locks** compitiendo por los rate limits de las APIs.
5. **Riesgos de trading**: kill-switch que no detiene el scalping, órdenes no idempotentes, cierres locales aunque falle el exchange, y DAYTRADING live que vende en Binance sin haber comprado nunca.

El módulo de ballenas — la pieza más diferenciadora del producto — muestra además **datos simulados presentados como reales** (PnL) y una **feature entera rota** (patrones aprendidos que nunca matchean).

---

## 2. 🔴 Seguridad — urgente (actuar hoy)

| # | Hallazgo | Dónde | Acción |
|---|----------|-------|--------|
| 1 | **Google OAuth client_id + secret reales commitados** en repo público | `.env.example` (raíz) y `criptodash/.env.example:17-18` | Revocar en Google Cloud Console, generar credenciales nuevas, poner placeholders. Purgar historia git (git-filter-repo ya está en requirements). |
| 2 | **Password MySQL `retsam77`** en texto plano | `setup.sh:29` y ambos `.env.example` | Rotarla en el VPS y parametrizar el script. |
| 3 | **API keys reales Binance/Bybit en disco** en un archivo muerto | `dashboard/config.py` (no trackeado, no importado por nadie) | Borrar el archivo. Verificar que `criptodash.zip` (13.9 MB, versionado) no lo contiene. |
| 4 | **DEBUG=True + ALLOWED_HOSTS=\*** en el `.env` efectivo; `DEBUG` con default True si falta la clave | `settings.py:36` | Forzar `DEBUG=False` salvo variable explícita; validar el `.env` del VPS. |
| 5 | **Vistas anónimas que disparan trabajo síncrono pesado** (DoS) | `ejecutar_analisis_trading` (`views/trading_views.py:16`), `run_bot_view` (`:41`), `import_data` (`data_views.py:16`), `technical_analysis`, app Dash en `/django_plotly_dash/` | `@login_required` + `@require_POST` donde aplique. |
| 6 | **Traceback completo devuelto al navegador con HTTP 200** | `whale_views.py:142-150` | Devolver 500 con página de error; loguear con ruta absoluta (hoy `whale_debug.log` depende del CWD). |

---

## 3. 🐋 Módulo de ballenas (foco principal)

### 3.1 Arquitectura actual

**Fuentes**: Solana RPC público sin API key (`services.py:17-43`), Etherscan V2 (`services.py:62-176`), Hyperliquid (`services.py:178-238`), Binance vía ccxt para contexto de mercado (`whale_intelligence.py`), DexScreener, GeckoTerminal, CoinGecko, Jupiter.

**Flujo**: `sync_all_whales_task` (beat 15 min) → `sync_wallet_task` por wallet → trackers crean `WhaleTransaction` → `PatternEngine.analyze_wallet` clasifica y dispara `_automated_shadow_trade` (crea `ShadowTrade` + `PatternInsight` + alerta Telegram) → consenso (`check_and_fire_consensus_signal`) → enriquecimiento retroactivo → aprendizaje de patrones (`WhalePatternLearner`) → scoring bajo demanda (`whale_scores_ajax`) → UI por AJAX.

**Problema de organización**: la lógica está repartida entre `whale_views.py` (1222 líneas), `services.py` (1095 líneas, mezcla trackers de API con analytics), `whale_analysis.py`, `whale_scoring.py`, `whale_intelligence.py`, `whale_pattern_learner.py` y `whale_signal_service.py` (completamente muerto).

### 3.2 Bugs críticos

1. **PnL falso mostrado como real** — `get_wallet_pnl` (`services.py:293-318`) es un placeholder confeso: `roi = conf*15`, `pnl_usdt = conf*1200` (aleatorio según "confianza"). Alimenta `whale_scores_ajax` y la métrica "PNL SIMULADO" del dashboard. Los datos reales existen en `ShadowTrade` cerrados (`pnl_percent`, `closed_at`) — solo hay que agregarlos.
2. **Patrones aprendidos inertes (feature rota)** — `WhalePatternLearner._save_patterns` (`whale_pattern_learner.py:234-247`) guarda condiciones como etiquetas (`{'rsi_14': 'oversold'}`); el branch numérico nunca se ejecuta. `WhalePattern.match_context` compara `32.5 == 'oversold'` → **siempre False** → `generate_signal` siempre HOLD → los patrones filtrados en `whale_insights` nunca matchean. Fix: guardar operadores (`rsi_14__lt: 30`).
3. **`whale_live_metrics` lanza FieldError** — `whale_views.py:1047-1048` usa `Avg('pnl_pct')` y `Sum('pnl_usd')`; los campos reales son `pnl_percent` y `pnl_usd` no existe.
4. **Ventas EVM nunca cierran shadow trades** — `services.py:165-166`: `from_asset` y `to_asset` se ponen iguales a `tokenSymbol`; `tx_type` es SWAP/TRANSFER según dirección, pero `analyze_wallet` solo procesa `tx_type=='SWAP'` como cierre. Las ventas quedan sin cerrar.
5. **Filtro de seguridad de tokens es no-op permanente** — `verify_token_security` (`services.py:631-649`) lee `raw_data['liquidity']`/`fdv`, claves que **nunca existen** en los raw_data de Solana ni EVM.
6. **Race conditions** — sin locks en todo el módulo: sync duplicado por beat + systemd + triggers manuales; reset de `SYNCING` sin campo `sync_started_at` (`tasks.py:99-102`); `exists()-then-create()` en los 3 trackers y en `_automated_shadow_trade` (`services.py:721-727`); consenso no idempotente (`services.py:905-935`).
7. **Wallets en ERROR nunca se recuperan** — el beat filtra `sync_status='IDLE'` (`tasks.py:109`) y nada resetea ERROR→IDLE.
8. **GET con efecto secundario** — `?sync=1` encola sync (`whale_views.py:61-68`); un crawler puede disparar syncs.
9. **`startCopyTrade` envía `price=1.0` fijo** (`whale_insights.html:527-542`) — shadow trade falso; usar `fetch_current_price`.
10. **`close_shadow_trade` divide por `entry_price` sin guard** (`shadow_views.py:65`).
11. **Falsos positivos en `target_pairs__icontains`** (`whale_views.py:56`) — "SOL" matchea "SOLIDUS".
12. **`get_whale_history` con ramas if/else idénticas** (`whale_views.py:319-326`).

### 3.3 Performance

- **N+1 confirmado en `whale_scores_ajax`** (`whale_views.py:469-496`): 2 `.get()` por wallet + ~10 queries más por wallet en cache-miss → ~12N queries por request.
- **`whale_trade_chart_ajax`** (`whale_views.py:792-997`): cascada síncrona de 4 APIs + Plotly sin caché y **sin `@ajax_rate_limit`** (único endpoint AJAX de ballenas sin decorador).
- **`trigger_whale_hunt` ejecuta la caza síncronamente en la request** (`whale_views.py:578-584`) — bloquea el worker web decenas de segundos.
- **Índice faltante crítico**: `WhaleTransaction(to_asset, timestamp)` — la query de consenso (`services.py:889-898`) se ejecuta tras cada sync por cada token objetivo → full scan de la tabla más grande del sistema. También faltan `PatternInsight(detected_at)` y `WhaleWallet(is_active, sync_status)`.
- `sync_all_whales_task` bloquea un worker con `time.sleep` entre batches (`tasks.py:141-168`).
- `whale_insights` ejecuta 5 queries muertas por página (insights, patterns, pairs, hot_tokens, top_whales — el template nuevo no las renderiza).

### 3.4 Duplicación y código muerto

- `get_top_whales` definido **dos veces** en `whale_scoring.py` (100-125 y 335-368); la segunda pisa a la primera. `get_whale_score`/`update_all_whale_scores` en `services.py:980-1015` duplican la API del engine sin callers.
- Lista de stablecoins duplicada en **6 sitios**; `TOKEN_MAP` de mints duplicado (`services.py:247-253` y `335-354`); dispatch de sync duplicado (`tasks.py:31-41` vs `sync_whales_background.py:49-60`).
- **Código muerto**: `WhaleSignalService` completo (solo lo usa un script raíz), `WhalePerformanceTracker` (`whale_scoring.py:371-450`), `analyze_wallet_task` (nadie la encola), vista `learn_patterns` (síncrona, sin UI), endpoints del template viejo (`whale_live_prices`, `search_tokens_ajax`, `whale_hot_tokens_ajax`, `whale_consensus_ajax`, `whale_live_metrics`, `suggest_bot_from_whale`), `whale_insights_old.html` (2100+ líneas), `whale_diagnostic.py` (referencia módulos y URL names inexistentes).
- admin.py no registra **ningún** modelo de ballenas.

### 3.5 Reorganización propuesta

Crear paquete `dashboard/whale/`:

```
dashboard/whale/
├── constants.py      # STABLES, TOKEN_MAP, rangos de indicadores (unificados)
├── trackers/         # solana.py, evm.py, hyperliquid.py (sacados de services.py)
├── pipeline.py       # _automated_shadow_trade, _close_shadow_trade, consenso, DNA
├── scoring.py        # WhaleScoringEngine (una sola API)
├── analysis.py       # whale_analysis.py
├── context.py        # whale_intelligence.py (cache en Django cache)
└── learner.py        # whale_pattern_learner.py
```

- `services.py` queda solo con lo que no es de ballenas, o desaparece.
- **Unificar el scheduler**: eliminar `whale_tracker.service` + `sync_whales_background.py` (el VPS ya corre Celery Beat) — hoy hay 3 productores compitiendo por los rate limits de Etherscan.
- Precalcular scores en tarea beat (5-10 min) y que `whale_scores_ajax` solo lea caché.
- Eliminar archivos muertos: `services.py.backup`, `whale_insights_old.html`, `whale_signal_service.py`, `simulate_whale_view.py`, `run_whale_learning.py` (o convertirlo en management command).

### 3.6 Mejoras priorizadas (ballenas)

**Alto**: (1) PnL real desde ShadowTrade; (2) arreglar patrones (operadores, no etiquetas); (3) fix `whale_live_metrics`; (4) corregir tracker EVM (ventas cierran trades); (5) locks por wallet (`cache.add`) + `sync_started_at` + reencolar ERROR; (6) eliminar doble scheduler; (7) índice `(to_asset, timestamp)`; (8) cachear + rate-limitar el chart; (9) quitar queries muertas y traceback al navegador.

**Medio**: (10) `target_pairs` CSV → JSONField o tabla; (11) alimentar `verify_token_security` con datos reales o eliminarlo; (12) precálculo de scores; (13) registrar modelos en admin; (14) panel de hunt targets y consenso en el template nuevo (los CRUD existen pero son inaccesibles); (15) `time.sleep` → `apply_async(countdown=...)`; (16) fix `startCopyTrade` con precio real.

**Bajo**: (17) borrar duplicados de métodos; (18) `ajax_rate_limit` con `cache.add` atómico; (19) `bulk_import_whales` con `get_or_create` en batch; (20) guard en `close_shadow_trade`; (21) paginar `export_whale_history`; (22) reescribir `whale_diagnostic.py` como management command.

---

## 4. 🤖 Bots y scalping — riesgos críticos

1. **Kill-switch no detiene el scalping** — `emergency_stop_all` (`bot_manager.py:700-781`) solo itera `LiveBot`. Ninguna tarea de scalping lee `GlobalSettings.kill_switch_active`. Si el botón de emergencia se activa, los scalping bots **siguen operando y colocando órdenes reales**.
2. **Cierre local aunque falle el exchange** — `_close_trade` (`bot_manager.py:580-593`) loguea el fallo de la venta real y cierra igualmente el trade local → posición real huérfana. Mismo patrón en `check_scalping_positions_task` (`tasks.py:578-594`) y `scalping_close_trade`.
3. **DAYTRADING live: vende sin comprar** — `_manage_daytrading_bot` nunca hace `create_order` de entrada (`bot_manager.py:548-566`), pero `_close_trade` sí vende a mercado si `is_live`. Contabilidad local ficticia vs ventas reales.
4. **Órdenes sin `clientOrderId`** — un retry tras timeout puede duplicar órdenes reales en Binance.
5. **Sin locks en todo el ciclo** — cero `select_for_update`; `run_bots` (systemd) + `trigger_bot_update` (web) + scripts raíz pueden ejecutar ciclos concurrentes → órdenes duplicadas. Ídem scalping: check-then-create no atómico (`tasks.py:402-405`).
6. **`edit_bot` cancela WAITING en DB sin cancelar las órdenes limit reales** (`bot_views.py:325-329`) — quedan vivas en Binance y no devuelve el balance.
7. **`trigger_balance_sync` corrompe la contabilidad** (`bot_views.py:398-445`): reescribe `initial_balance` (historia), fija negativos a 1.0 ("oculta pérdidas reales") y re-escala todos los balances por ratio.
8. **`check_global_risk` es fail-open** (`bot_manager.py:695-697`): excepción → `return True` (seguimos operando). El drawdown ignora pérdidas flotantes.
9. **Contadores sin `F()`** — `bot.total_trades += 1` con varios workers pierde actualizaciones (`tasks.py:483-484`).
10. **Tres clientes ccxt distintos** — `ccxttest1.py:35` (sin `enableRateLimit`), `pair_scanner.py:31` (instancia nueva por llamada, una por bot por minuto), `utils/performance.py:41`.

**Mejoras alto impacto**: locks + `transaction.atomic` en el ciclo de bots; kill-switch para scalping; `clientOrderId` idempotente; no cerrar local si falla el exchange (estado `CLOSE_FAILED` + alerta); cancelar órdenes reales al editar; prohibir DAYTRADING live hasta tener la compra real; fail-closed en el risk check; refund de balance en cancelaciones.

**Mejoras medio**: unificar cliente exchange en `dashboard/exchange/client.py`; fusionar `DayTradingStrategy`/`OptimizedDayTradingStrategy`; borrar `bot_trading.py` y `EnhancedRiskManager` (muertos); heartbeat `last_run_at` para detectar bots zombies; mover los ~120 scripts raíz a management commands.

---

## 5. 🗄️ Infraestructura y datos

### 5.1 Modelo de datos

- **Doble sistema de pares**: `TradingPair` (bots clásicos) vs `Pair` (scalping) — terminar la migración (`backfill_pairs.py`) y deprecar `TradingPair`.
- **Índices faltantes**: `WhaleTransaction(to_asset, timestamp)`, `PairScanResult(scanned_at)` (cleanup diario con full scan creciente, ~5.5k filas/día), `OHLCVData(pair, timeframe, timestamp)`.
- **Índice redundante**: `Pair` declara `Index(['symbol'])` cuando `symbol` ya es unique.
- **Drift modelo↔migraciones**: `ScalpingTrade.Meta.indexes = [Index(['status','bot'])]` (`models.py:586-588`) **nunca fue migrado** — `check_scalping_positions_task` hace full scan cada 30 s.
- **Raw SQL muerto** en `ccxttest1.py:228-244` con hosts hardcodeados y f-strings inyectables.
- Los 14 modelos nuevos (ballenas, scalping, consensus, GlobalSettings…) no están en admin.

### 5.2 Celery

- Schedule en código (settings.py:305-341), estado del beat en `celerybeat-schedule` (SQLite en CWD) → basura versionada y git dirty permanente si el VPS despliega por git.
- **Sin locks en ninguna tarea**; `acks_late` no configurado (trabajo perdido si muere el worker); tareas largas sin `time_limit` (`retroactive_context_enrichment_task` con `sleep(0.3)` por tx puede correr horas); `max_retries=2` declarado pero nunca `self.retry()`.
- **Errores silenciosos**: varias tareas devuelven `{'error': ...}` → SUCCESS; trackers tragan todo (`except: return []`) — fallo de API indistinguible de "no hay transacciones".
- `sync_wallet_task` es la única que re-lanza excepciones correctamente.

### 5.3 Migraciones (39 archivos, 0001–0038)

- **Diamante `0002` válido para Django** (dos migraciones `0002_*` con nombres completos distintos, un único nodo hoja 0038, 0004 con dos padres). **Pero** operativamente problemático: `migrate dashboard 0002` falla con ambigüedad; `squashmigrations` se confunde; renombrar los archivos rompería producción (Django los vería como no aplicados).
- `0002_remove_indicators_constraint.py` es artesanal y no-op (operations comentadas).
- **0004/0005 son MySQL-only** (`ALTER TABLE ... MODIFY ... LONGTEXT`) — un migrate desde cero en SQLite/PostgreSQL falla.
- **Riesgo real de producción**: hay SQL aplicado a mano (los `.sql` sueltos de la raíz: `change_to_text.sql`, `fix_constraint.sql`, `drop_check_alt.sql`). **Antes de cualquier deploy**: correr `showmigrations dashboard` en el VPS y compararlo con el repo — si algo se fakeó a mano, el `RenameIndex` de 0003 puede reventar.
- Acciones: generar la migración pendiente del índice de `ScalpingTrade`; añadir `makemigrations --check --dry-run` al flujo de deploy; consolidar 0001→0038 con `squashmigrations` en ventana de mantenimiento.

### 5.4 Deployment VPS

- Los units systemd reales (`criptodash-daphne.service`, `celery-beat.service`, `celery-worker.service`, `criptobots.service`) **no están versionados** — la configuración de producción no es reproducible. `whale_tracker.service` (el único en el repo) apunta a una ruta vieja y duplica el sync de ballenas.
- `criptobots.service` (run_bots con órdenes LIVE) y el scalping de Celery operan **la misma cuenta Binance sin coordinación** — riesgo de doble exposición de capital.
- **Drift de versiones**: el `nohup.out` del VPS muestra `runserver` (¡dev server!) con Django 6.0.3 en julio, mientras requirements pin Django 5.2.7.
- Channels/Daphne con **cero `group_send`** en todo el proyecto — el "tiempo real" es polling. O se cablea `group_send` desde las tareas, o Channels es peso muerto.
- Basura de runtime versionada: `staticfiles/` completo, `logs/` (6.5 MB), `celerybeat-schedule*`, `data_migration.json` ×2 (71 MB), `criptodash.zip` (13.9 MB), `get-pip.py` (2.2 MB).
- `CACHES` comparte Redis DB 0 con broker/results de Celery (`settings.py:162-167`) — separar.
- Dos `requirements.txt` idénticos (freeze completo con herramientas dev y librerías no usadas: Flask, SQLAlchemy, dash).

---

## 6. 🧹 Higiene del repositorio

- **~116 scripts .py sueltos en `criptodash/`** (~10k líneas): solo `sync_whales_background.py` está en producción (referenciado por `whale_tracker.service`). ~80 son desechables (debug_\*, diag_\*, inspect_\*, check_\*, fix_\*, verify_\*, test_\*, vps_\* salvo `vps_security_audit`) — **ninguno es referenciado por systemd, celery, cron ni código** (verificado): borrables con riesgo cero vía `git rm`. Ojo: `fix_endif.py` reescribe templates con replace de strings — no conservar.
- **Archivos muertos**: `dashboard/views_old.py` (1107 líneas, ignorado por git, cero imports), `services.py.backup` (1051, trackeado), `estilos.py` + `plot.py` (solo importados sin usar por `ccxttest1.py:14,32`), `settings.py` muerto en raíz de criptodash, 6 `.sql` sueltos, `test_sinc_now.py` (corrompido), varios scripts con paths absolutos de Windows.
- **Tests: cero.** `dashboard/tests.py` está vacío; no hay pytest ni coverage; los 28 `test_*.py` son scripts manuales. `whale_views.py` (1222 líneas) y `bot_views.py` (677) no tienen ningún test automatizado.
- **Basura versionada (495+ archivos)**: `.pyc`, `celerybeat-schedule*`, `nohup.out`, logs, `staticfiles/`, zips, JSONs de migración, `stats/`, `landing/`, `index.php.bak`. `.gitignore` los cubre hoy, pero fueron commiteados antes → `git rm --cached` + ampliar patrones (falta `celerybeat-schedule*`, `*.zip`, `*.backup`, `logs/`, `view_error*`…).
- `TODO.md`: solo 4 pendientes menores del servicio de ballenas (validación del `--loop` de `sync_whales_background.py` — que proponemos eliminar).
- Prácticas: logging correcto en los módulos principales; quedan `except: pass` sin loguear en `bot_manager.py:372,484`, `services.py:29,42,288,534,648,741`, `backtester.py:295`, `tasks.py:72`, `whale_analysis.py:142`.

---

## 7. Plan de acción por fases

### Fase 0 — Seguridad (esta semana)
1. Revocar Google OAuth secret/client id → nuevos, placeholders en `.env.example`, purgar historia git.
2. Rotar password MySQL `retsam77` en el VPS; parametrizar `setup.sh`.
3. Borrar `dashboard/config.py`; verificar `criptodash.zip`.
4. `DEBUG=False` forzado en producción; validar `.env` del VPS.
5. `@login_required` en las 4 vistas anónimas pesadas.
6. En el VPS: `showmigrations dashboard` y diff con el repo antes del próximo deploy.

### Fase 1 — Ballenas (prioridad del usuario)
1. PnL real desde `ShadowTrade` cerrados (reemplazar placeholder).
2. Arreglar patrones aprendidos (operadores vs etiquetas).
3. Fix `whale_live_metrics` (FieldError).
4. Corregir tracker EVM (ventas cierran shadow trades).
5. Locks de sync + `sync_started_at` + recuperación de wallets ERROR.
6. Eliminar `whale_tracker.service`/`sync_whales_background.py` (un solo productor: Celery).
7. Índice `WhaleTransaction(to_asset, timestamp)` (+ los otros).
8. Reorganizar en paquete `dashboard/whale/` (trackers, pipeline, scoring, analysis, context, learner, constants).
9. Cachear + rate-limitar `whale_trade_chart_ajax`; caza en background.
10. Quitar queries muertas y el traceback al navegador; arreglar `startCopyTrade`.

### Fase 2 — Trading
1. Locks + transacciones en el ciclo de bots y scalping.
2. Kill-switch efectivo para scalping.
3. `clientOrderId` idempotente; no cerrar local si falla el exchange.
4. DAYTRADING live: compra real o prohibir `is_live`.
5. Cancelar órdenes reales en `edit_bot`; sanear `trigger_balance_sync`; fail-closed en risk check; `F()` en contadores.
6. Unificar cliente ccxt y las dos estrategias DayTrading.

### Fase 3 — Infraestructura e higiene
1. `git rm --cached` de basura versionada + ampliar `.gitignore`.
2. Borrar ~80 scripts desechables y archivos muertos (views_old, services.py.backup, estilos, plot).
3. Versionar los units systemd reales del VPS.
4. Migración pendiente del índice `ScalpingTrade`; `makemigrations --check` en deploy; plan de squash.
5. Registrar los 14 modelos en admin.
6. Tests reales (empezar por las vistas de ballenas y bots).
7. Separar requirements prod/dev; separar caché de broker; alinear Django en el VPS.

---

*Informe generado con 4 exploraciones paralelas del código (ballenas, bots/scalping, infraestructura, higiene). Todas las referencias file:line están verificadas contra el árbol actual.*
