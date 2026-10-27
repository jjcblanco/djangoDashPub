# 🐋 Guía completa — Whale Tracker Pro

> Módulo de seguimiento de ballenas, análisis de patrones y caza de smart money de CriptoDash.
> Ruta: `/whale-insights/` (requiere estar logueado).

---

## 1. Qué es

Whale Tracker Pro monitorea billeteras de gran capital ("ballenas") en 5 blockchains,
analiza su comportamiento y genera señales accionables:

- **Seguimiento** de wallets en: `Solana`, `Ethereum`, `Base`, `BNB Chain (BSC)`, `Hyperliquid`.
- **Análisis de comportamiento**: clasifica cada ballena (acumulador, trader, distribuidor…).
- **Win rate por moneda**: en qué tokens gana cada ballena.
- **Patrones aprendidos**: RSI de compra preferido, mejor indicador, horarios de actividad.
- **Caza automática (Hunt)**: descubre nuevas ballenas a partir de contratos de tokens.
- **Señales de consenso**: 3+ ballenas comprando el mismo token en poco tiempo.
- **Flujos CEX**: depósitos/retiros de ballenas hacia exchanges (intención de mercado).
- **Shadow Trading**: simulación de copy-trade para validar sin arriesgar capital.
- **Gráfico con trades superpuestos** sobre el precio, con EMA/RSI/MACD.

---

## 2. Conceptos clave

| Concepto | Descripción |
|---|---|
| **Ballena (WhaleWallet)** | Wallet que el sistema sigue. Tiene dirección, red, categoría, filtro y pares objetivo. |
| **Categoría** | `DCA` (acumulación), `SNIPER`, `SMART_MONEY`, `INSIDER`, `OBSERVATION`. Es una etiqueta que eliges tú al seguir. |
| **Filtro** | `OPEN` = registra todo; `STRICT` = solo tokens estables (whitelist). |
| **target_pairs** | Tokens en los que opera la ballena (ej. `SOL,WIF,PEPE`). Se descubren automáticamente al sincronizar y alimentan el filtro de par. |
| **Sync** | Descarga de transacciones recientes de la wallet (100 txs normal, 500 en sync profunda). |
| **Enriquecer historial** | Recalcula el contexto de mercado (RSI, MACD, BB, SMA, volumen) en el instante exacto de cada transacción pasada. Es **requisito previo** para aprender patrones. |
| **Shadow Trade** | Operación simulada: se abre al precio real de mercado y se cierra manualmente; el PnL % alimenta las métricas. |
| **Hunt Target** | Contrato de token a escanear para descubrir ballenas compradoras. |
| **Señal de consenso** | 3+ ballenas seguidas compraron el mismo token en un período corto. |
| **Flujo CEX** | Movimiento entre una ballena y una hot wallet de exchange: `DEPOSIT` → presión vendedora; `WITHDRAWAL` → posible compra en DEX. |

---

## 3. Recorrido por la interfaz

### 3.1 Barra superior

| Botón | Qué hace |
|---|---|
| **🌐 Filtro de par** | Desplegable con todos los tokens de todas las wallets. Filtra la lista de ballenas y los shadow trades abiertos. Se quita con la ✕. |
| **🎯 Cazar** | Lanza la caza de ballenas sobre todos los Hunt Targets activos (en background). Recarga la página al terminar. |
| **🔄 Sync** | Encola la sincronización masiva de todas las wallets activas (background). También ocurre **automáticamente cada 15 min**. |
| **➕ Seguir** | Abre el modal para seguir una wallet individual. |
| **📥 Importar** | Modal de importación masiva (una dirección por línea). |
| **🤖 Bots / ⚡ Scalping** | Accesos rápidos a los otros módulos. |

### 3.2 Panel de métricas (arriba)

- **Ballenas seguidas** — total de la lista (máximo 50 visibles).
- **Win rate promedio** — media de win rate de las wallets con datos cacheados.
- **PnL simulado** — suma del PnL de los shadow trades cerrados (nocional × pnl%).
- **Señales activas** — señales de consenso en estado `ACTIVE`.

### 3.3 Panel "Hunt Targets" (caza de ballenas)

- Lista los contratos que se escanean en busca de compradores grandes.
- **➕ Añadir**: símbolo, blockchain, dirección de contrato y **volumen mínimo en USD**
  (solo se agregan wallets cuyo volumen de compra supere ese mínimo).
- **⏸/▶** pausa o activa un target sin borrarlo; **🗑** lo elimina.
- Si la tabla está vacía, la primera caza siembra targets por defecto:
  WIF, BONK, JUP (Solana), PEPE, SHIB (Ethereum), TOSHI (Base).
- El botón **Cazar** escanea todos los targets activos, crea las ballenas nuevas
  (nombre `Hunter: SYMBOL #abc123`, categoría Observación), les asigna el token como
  `target_pairs` y dispara su sync inmediata. Envía alerta por Telegram por cada hallazgo.
- La caza también corre **automáticamente cada 6 h** (solo alto volumen y ≥2 txs).

### 3.4 Señales de Consenso 🔥

Aparece solo si hay señales activas. Cada tarjeta muestra token, nº de ballenas y
confianza, con botón **＋** que precarga ese token en el formulario de Hunt Targets.

### 3.5 Flujos CEX 🏦

Depósitos/retiros recientes entre ballenas seguidas y exchanges conocidos.
Rojo `→` = depósito al CEX (posible venta); verde `←` = retiro (posible compra en DEX).
Los flujos que superan el umbral de USD disparan alerta por Telegram.

### 3.6 Sidebar izquierdo — lista de wallets

Cada fila muestra: nombre, red, nº de txs, nº de simulaciones, última sync, etiquetas de
tokens (`$SOL`, clicables para filtrar), badge de comportamiento, win rate y **score**:

- **Score** (puntos): ≥70 fondo verde, ≥40 amarillo. Lo calcula `WhaleScoringEngine`
  y se refresca cada 6 h (y por demanda vía AJAX).
- **Caja de búsqueda** filtra client-side por nombre/dirección/token.
- Botones del encabezado:
  - **🧠 Aprender patrones** — aprendizaje ampliado en background (usa transacciones
    enriquecidas + shadow trades cerrados; mínimo 3 muestras y 55 % win rate).
  - **🗄 Enriquecer historial** — enriquece el contexto de mercado de **todas** las
    wallets (background, puede tardar minutos).

### 3.7 Panel de detalle (clic en una wallet)

#### Cabecera
- Nombre, red y dirección (clic para **copiar**).
- **Sync** — sincronización profunda de esta wallet (200 firmas en Solana / 500 txs).
- **Gráfico**, **CSV** (exportar historial) y **🗑** (dejar de seguir, borrado físico).

#### Comportamiento & DNA
Clasifica la wallet en un modo:

| Modo | Icono | Significado |
|---|---|---|
| Acumulador DCA | 🏦 | Mayormente compras progresivas, pocas ventas. |
| Trader Activo | ⚡ | Alta rotación compra/venta equilibrada. |
| Swing Trader | 🌊 | Rotación media con holds más largos. |
| Distribución | 📤 | Más ventas que compras (fase de salida). |
| En Observación | 👁️ | Datos insuficientes todavía. |

Además muestra: ratio compra/venta, nº de txs, hold promedio, **RSI promedio al comprar**
(verde <40 = compra en miedo; rojo >60 = compra euforia), horas activas e indicadores
que más usa (chips).

#### Win Rate por Moneda
Tabla por token: nº de trades, win rate, PnL medio % y última operación.
Colores: WR ≥60 verde, 40–60 amarillo, <40 rojo.

#### Copy Trade (Shadow Trading)
- **🔬 Simulado (Shadow)**: abre un ShadowTrade al **precio real de mercado** del primer
  par de la ballena (amount = 1 token). Lo verás abajo con botón **Cerrar**, que cierra
  al precio actual y registra el PnL %.
- **⚡ Real (Binance)**: pide confirmación extra; hoy también abre la simulación — la
  ejecución de órdenes reales se gestiona desde el módulo de Bots.

#### Patrones & Indicadores
Mejor patrón detectado y desglose de **win rate por rango de RSI al comprar**
(ej. "RSI 30–40: 72 % WR en 14 trades"), basado en N operaciones con contexto de mercado.

#### Últimas Operaciones
Últimas 15 transacciones con tipo (BUY/SWAP/…), activos, fecha y enlace al explorador
(Solscan, Etherscan, Basescan o Hyperliquid según la red).

#### Gráfico (botón Gráfico)
- Precio del token (velas 1h de **Binance** si existe; si no, fallback a
  DexScreener + GeckoTerminal en diario).
- Indicadores: **EMA 9/21/50/200, RSI(14) y MACD**.
- **Trades de la ballena superpuestos** (compras y ventas como marcadores).
- Selector de token para cambiar entre los tokens que la wallet ha operado.
- Se cachea 10 min por wallet+token.

---

## 4. Flujo de trabajo recomendado (paso a paso)

### Paso 1 — Seguir ballenas
- **Manual**: ➕ Seguir → dirección, nombre, red, categoría, filtro y token objetivo.
- **Masivo**: 📥 Importar → pega varias direcciones (una por línea), elige red y
  categoría, y marca **"Auto-sincronizar después de importar"**. Recibirás aviso por
  Telegram con el resumen.
- No se permiten duplicados de (dirección + red).

#### ¿De dónde sacar direcciones de ballenas?

Si no tienes direcciones a mano, estas son las fuentes más efectivas (todas gratis
o con plan gratuito suficiente). **DexScreener y GeckoTerminal son las mismas fuentes
que usa el cazador interno del sistema**, así que lo que veas ahí es exactamente lo
que el Hunt automático encontraría.

| Fuente | Redes | Qué buscar |
|---|---|---|
| **DexScreener** (`dexscreener.com`) → busca el token → pestaña **Top Traders** | Todas | Ranking de compradores/vendedores recientes con dirección y volumen. Copia las direcciones de los que más compraron. |
| **GeckoTerminal** (`geckoterminal.com`) → pool del token → **Top traders** | Todas | Compradores recientes del pool con monto. Misma data que usa la caza interna (vía API). |
| **Solscan** (`solscan.io`) → token → pestaña **Holders** / **Top Traders** | Solana | Holders más grandes y traders más activos del token. |
| **Etherscan** (`etherscan.io`) → token → **Holders** | Ethereum | Top 500 holders del token (gratis). Filtrá los que tengan transacciones recientes. |
| **BscScan** (`bscscan.com`) → token → **Holders** | BNB Chain | Top holders con actividad reciente. |
| **BaseScan** (`basescan.org`) → token → **Holders** | Base | Top holders con actividad reciente. |
| **GMGN** (`gmgn.ai`) → token → sección **Smart Money** | Solana, EVM | Wallets etiquetadas como smart money que operaron el token. |
| **Hyperliquid Explorer** (`app.hyperliquid.xyz/explorer`) → leaderboard | Hyperliquid | Direcciones de los traders más rentables de la plataforma. |
| **Arkham** (`arkhamintelligence.com`) | Multi-cadena | Búsqueda de entidades y wallets etiquetadas (ballenas, fondos, CEX). |
| **Cuentas de X/Twitter** (@lookonchain, @whale_alert, @EmberCN) | Todas | Publican direcciones concretas de ballenas con la tx que acaban de hacer. Copiá la dirección y pegala. |

**Antes de pegar, validá rápido:**

- **Formato correcto por red**: EVM (Ethereum/Base/BSC/Hyperliquid) empieza con `0x` y
  tiene 42 caracteres; Solana es base58 de 32–44 caracteres sin `0x`. El sistema
  normaliza minúsculas en EVM automáticamente.
- **Que sea una wallet, no un contrato**: si en el explorador dice "Contract", no sirve.
  Buscá cuentas con transacciones (EOA).
- **Actividad reciente**: abrí la dirección en el explorador y confirmá que operó en
  los últimos días. Una wallet sin txs recientes no aporta señales.
- **Historial de trades, no solo un airdrop**: priorizá wallets con varias compras/ventas;
  son las que generan patrones y win rate útiles.

**Flujo rápido de descubrimiento manual:**

1. Elegí un token que te interese.
2. Abrí DexScreener o GeckoTerminal → **Top Traders** del token.
3. Verificá 2–3 candidatas en el explorador (actividad reciente, no contrato).
4. Copiá las direcciones y pegalas en **📥 Importar** (una por línea).
5. Marcá "Auto-sincronizar después de importar" para que el análisis arranque solo.

> 💡 La vía sin fricción es el **Hunt automático** (paso 6): el sistema escanea los
> contratos de Hunt Targets y agrega a los mayores compradores sin que copies nada.

### Paso 2 — Sincronizar
- Pulsa **🔄 Sync** (o espera al ciclo automático de 15 min).
- La primera sync trae las transacciones recientes y el análisis
  (`PatternEngine.analyze_wallet`) rellena `target_pairs`, `top_tokens` y `trading_dna`.
- Si una wallet necesita más historia: clic en ella → **Sync** (sync profunda).

### Paso 3 — Enriquecer historial
- Pulsa **🗄 Enriquecer historial** en la cabecera del sidebar.
- Esto reconstruye RSI/MACD/SMA/BB/volumen **en el momento de cada trade pasado**
  y es imprescindible para que el aprendizaje de patrones tenga material.

### Paso 4 — Aprender patrones
- Pulsa **🧠** en el sidebar.
- Si el dataset es insuficiente (<3 muestras), el sistema te lo dice y te sugiere
  enriquecer primero. Con datos suficientes, aprende en background y actualiza los
  patrones en unos minutos.

### Paso 5 — Analizar
- Revisa el **score** y los badges de la sidebar: prioriza ballenas ≥70 pts con
  WR alto y modo Acumulador o Swing.
- Abre cada ballena: mira **Comportamiento & DNA** y **Win Rate por Moneda**.
- Vigila **Señales de Consenso**: si 3+ ballenas compran lo mismo, es candidato a bot.
- Vigila **Flujos CEX**: depósito grande = cuidado con venta; retiro = posible compra.

### Paso 6 — Cazar ballenas nuevas
- Añade contratos en **Hunt Targets** (o deja los sembrados por defecto).
- Pulsa **🎯 Cazar** y espera el resultado; las nuevas ballenas aparecen con sync
  ya disparada. La caza automática cada 6 h mantiene el flujo sin intervención.

### Paso 7 — Validar con Shadow Trading y exportar
- Con una ballena seleccionada, abre una simulación en **Copy Trade** sobre su par.
- Ciérrala cuando lo decidas; el PnL % quedará registrado y alimentará win rate y
  patrones.
- Usa **CSV** para llevarte el historial completo (incluye los indicadores de contexto
  por trade) y **Gráfico** para revisar entradas/salidas contra el precio.

---

## 5. Automatización (Celery Beat)

| Tarea | Frecuencia |
|---|---|
| Sincronización de todas las ballenas | Cada **15 min** |
| Caza automática de ballenas (alto volumen, ≥2 txs) | Cada **6 h** |
| Señales desde patrones aprendidos | Cada **15 min** |
| Re-cálculo de scores de ballenas | Cada **6 h** |

**Requisito**: Redis + Celery worker + Celery Beat corriendo (en el VPS son servicios
systemd). Si no corren, las acciones "en background" (Sync, Cazar, Enriquecer,
Aprender) devuelven error al encolar y las métricas quedan en "Cargando…".

Detalles de robustez ya incorporados:
- **Lock por wallet**: si una wallet ya está sincronizándose, se omite la tarea
  duplicada (evita solapes entre beat, cron y triggers manuales).
- **Auto-recuperación**: wallets colgadas en `SYNCING` >30 min se liberan; wallets en
  `ERROR` se reintentan pasados 60 min.

---

## 6. Notas y límites a tener en cuenta

- La lista muestra las **primeras 50 wallets**; usa el buscador o el filtro de par
  para acotar.
- **BSC** usa un RPC público (`eth_getLogs`) sin API key — más lento y limitado que
  las demás redes; no requiere BscScan.
- Direcciones EVM (Ethereum/Base/BSC) se guardan en minúsculas; Solana tal cual.
- Las métricas de score/PnL vienen de caché (15 min); si ves "Calculando…", espera al
  AJAX de scores o al ciclo de 6 h.
- "Dejar de seguir" (🗑) es **borrado físico** de la wallet y su historial.
- El endpoint `/whale-insights/suggest-bot/<wallet_id>/` (API) devuelve parámetros
  sugeridos para crear un bot GRID/DayTrading a partir del historial de una ballena.

---

## 7. Solución de problemas

| Síntoma | Causa probable / solución |
|---|---|
| "Error al encolar tarea… ¿Está corriendo Redis/Celery?" | Redis o los workers de Celery están caídos. Levantar servicios y reintentar. |
| Métricas en "Cargando…" / "Calculando…" permanente | Celery sin correr o caché sin poblar; verificar worker + beat. |
| "Dataset insuficiente para aprender" | Ejecutar primero **🗄 Enriquecer historial** y esperar a que termine. |
| Wallet atascada en `SYNCING` o `ERROR` | Se auto-recupera (30/60 min) en el próximo ciclo de sync. |
| "No hay contratos activos en Hunt Targets" al cazar | Añadir al menos un target en el panel (o esperar la siembra automática). |
| Gráfico sin datos | El token no está en Binance y DexScreener/GeckoTerminal no devolvió OHLCV; probar con otro token del selector. |
| Página devuelve "Error interno" | Revisar logs del servidor (`logger.exception` en `whale_views`). |

---

## 8. Referencias de código (para desarrollo)

| Pieza | Archivo |
|---|---|
| Vista principal y endpoints AJAX | `criptodash/dashboard/views/whale_views.py` |
| Shadow trading (simular/cerrar/precios) | `criptodash/dashboard/views/shadow_views.py` |
| Plantilla del panel | `criptodash/dashboard/templates/dashboard/whale_insights.html` |
| Modelos (Wallet, Tx, Shadow, HuntTarget, Consensus, ExchangeFlow, Pattern) | `criptodash/dashboard/models.py` |
| Tareas Celery (sync, hunt, enriquecimiento, aprendizaje) | `criptodash/dashboard/tasks.py` |
| Trackers por red | `criptodash/dashboard/whale/trackers.py` |
| Clasificación de comportamiento | `criptodash/dashboard/whale/analysis.py` |
| Scoring | `criptodash/dashboard/whale/scoring.py` |
| Detección de flujos CEX | `criptodash/dashboard/whale/flows.py` |
| Schedule de Celery Beat | `criptodash/criptodash/settings.py` (`CELERY_BEAT_SCHEDULE`) |
