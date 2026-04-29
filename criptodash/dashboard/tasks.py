from celery import shared_task
import logging
import time
from django.utils import timezone
from dashboard.utils.notifications import send_telegram_message

logger = logging.getLogger(__name__)

@shared_task
def sync_wallet_task(wallet_id, deep_sync=False):
    """
    Sincroniza una única ballena en segundo plano.
    """
    from dashboard.models import WhaleWallet
    from dashboard.services import SolanaWhaleTracker, EVMWhaleTracker, HyperliquidWhaleTracker, PatternEngine
    
    try:
        wallet = WhaleWallet.objects.get(id=wallet_id)
        wallet.refresh_from_db()
        if not wallet.is_active:
            return f"Wallet {wallet_id} is inactive."
            
        # Marcar como sincronizando
        wallet.sync_status = 'SYNCING'
        wallet.save()
            
        new_txs = 0
        limit = 500 if deep_sync else 100
        
        if wallet.blockchain == 'solana':
            tracker = SolanaWhaleTracker()
            # Si es deep_sync, traemos más historial para analizar
            signatures_limit = 200 if deep_sync else 50
            new_txs = tracker.sync_wallet(wallet, max_new=limit, signatures_limit=signatures_limit)
        elif wallet.blockchain in ['ethereum', 'base']:
            tracker = EVMWhaleTracker(wallet.blockchain)
            new_txs = tracker.sync_wallet(wallet, max_new=limit)
        elif wallet.blockchain == 'hyperliquid':
            tracker = HyperliquidWhaleTracker()
            new_txs = tracker.sync_wallet(wallet, max_new=limit)
            
        # El análisis es costoso, por eso va en Celery
        PatternEngine.analyze_wallet(wallet)

        # --- FASE 2: Detección de Consenso ---
        # Después de analizar, verificar si este token ya lo compraron 3+ ballenas (señal de consenso)
        try:
            top_pairs = wallet.target_pairs_list  # ['WIF', 'JUP', ...]
            for token_symbol in top_pairs:
                PatternEngine.check_and_fire_consensus_signal(
                    symbol=token_symbol,
                    blockchain=wallet.blockchain
                )
        except Exception as e:
            logger.warning(f"[Consensus] Error en detección post-sync para wallet {wallet_id}: {e}")
        
        # Marcar como finalizado con éxito
        wallet.sync_status = 'IDLE'
        wallet.last_sync = timezone.now()
        wallet.save()
        
        logger.info(f"Successfully synced {new_txs} txs for wallet {wallet_id} ({wallet.blockchain}).")
        return new_txs
    except Exception as e:
        # Intentar marcar error si la wallet existe
        try:
            from dashboard.models import WhaleWallet
            w = WhaleWallet.objects.get(id=wallet_id)
            w.sync_status = 'ERROR'
            w.save()
        except:
            pass
            
        logger.error(f"Error syncing wallet {wallet_id}: {str(e)}")
        raise e

@shared_task
def sync_all_whales_task():
    """
    Encola la sincronización de todas las ballenas activas.
    Ideal para ser llamado por Celery Beat o un Cronjob cada X minutos.
    """
    from dashboard.models import WhaleWallet
    from datetime import timedelta
    
    # --- Recuperación de wallets bloqueadas en SYNCING ---
    # Si un wallet lleva más de 30 min en SYNCING, el worker probablemente murió.
    # Lo reseteamos a IDLE para que pueda volver a sincronizarse en el próximo ciclo.
    SYNCING_TIMEOUT_MINUTES = 30
    stale_threshold = timezone.now() - timedelta(minutes=SYNCING_TIMEOUT_MINUTES)
    stale_count = WhaleWallet.objects.filter(
        sync_status='SYNCING',
        last_sync__lt=stale_threshold  # last_sync es la última vez que terminó con éxito
    ).update(sync_status='IDLE')
    
    # También recuperar los que nunca se sincronizaron (last_sync=None) y llevan rato SYNCING
    # Esto ocurre si el worker murió justo en la primera sync
    also_stale = WhaleWallet.objects.filter(
        sync_status='SYNCING',
        last_sync__isnull=True
    ).update(sync_status='IDLE')
    
    total_recovered = stale_count + also_stale
    if total_recovered > 0:
        logger.warning(f"Recuperadas {total_recovered} wallets bloqueadas en SYNCING (timeout > {SYNCING_TIMEOUT_MINUTES} min).")
    
    # --- Encolar sincronización de todas las wallets activas ---
    active_wallets = WhaleWallet.objects.filter(is_active=True, sync_status='IDLE')
    
    # Separar por blockchain para manejar rate limits específicos
    wallets_by_blockchain = {}
    for wallet in active_wallets:
        chain = wallet.blockchain
        if chain not in wallets_by_blockchain:
            wallets_by_blockchain[chain] = []
        wallets_by_blockchain[chain].append(wallet)
    
    total_count = 0
    
    # Procesar cada blockchain con estrategias de rate limiting diferentes
    for blockchain, wallets in wallets_by_blockchain.items():
        logger.info(f"Procesando {len(wallets)} wallets de {blockchain}")
        
        if blockchain in ['ethereum', 'base']:
            # Ethereum y Base usan Etherscan API: rate limit estricto (5 calls/sec)
            # Procesar en batches de 5 con 1 segundo entre batches
            BATCH_SIZE = 5
            DELAY_SECONDS = 1.0
            
            for i in range(0, len(wallets), BATCH_SIZE):
                batch = wallets[i:i + BATCH_SIZE]
                
                # Encolar batch
                for wallet in batch:
                    sync_wallet_task.delay(wallet.id)
                    total_count += 1
                
                # Esperar entre batches si no es el último
                if i + BATCH_SIZE < len(wallets):
                    time.sleep(DELAY_SECONDS)
                    
        elif blockchain == 'solana':
            # Solana RPC puede tener rate limits
            # Procesar en batches de 10 con 0.5 segundos entre batches
            BATCH_SIZE = 10
            DELAY_SECONDS = 0.5
            
            for i in range(0, len(wallets), BATCH_SIZE):
                batch = wallets[i:i + BATCH_SIZE]
                
                for wallet in batch:
                    sync_wallet_task.delay(wallet.id)
                    total_count += 1
                
                if i + BATCH_SIZE < len(wallets):
                    time.sleep(DELAY_SECONDS)
                    
        else:
            # Hyperliquid y otros: menos restrictivos
            # Procesar más rápido pero con pequeño delay
            for i, wallet in enumerate(wallets):
                sync_wallet_task.delay(wallet.id)
                total_count += 1
                
                # Pequeño delay cada 5 wallets
                if i % 5 == 0 and i > 0:
                    time.sleep(0.2)
    
    logger.info(f"Encolada sincronización en background para {total_count} ballenas activas.")
    return total_count


# ───────────────────────────────────────────
# HUNTER DE BALLENAS POR PAR / TOKEN
# ───────────────────────────────────────────

# Targets por defecto usados como semilla si la BD está vacía
_DEFAULT_HUNT_TARGETS = [
    {'blockchain': 'solana',   'token_symbol': 'WIF',   'contract_address': 'EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm', 'min_volume_usd': 200},
    {'blockchain': 'solana',   'token_symbol': 'BONK',  'contract_address': 'DezXAZ8z7Pnrn9vzctrxEXpWMrNHqR1f6f69nL4XYUDx', 'min_volume_usd': 100},
    {'blockchain': 'solana',   'token_symbol': 'JUP',   'contract_address': 'JUPyiPZp718zay7kaPn2CoJvRwvpqcRuS5B7shuYf79',  'min_volume_usd': 500},
    {'blockchain': 'ethereum', 'token_symbol': 'PEPE',  'contract_address': '0x6982508145454ce325ddbe47a25d4ec3d2311933',      'min_volume_usd': 1000},
    {'blockchain': 'ethereum', 'token_symbol': 'SHIB',  'contract_address': '0x95aD61b0a150d79219dCF64E1E6Cc01f0B64C4cE',      'min_volume_usd': 1000},
    {'blockchain': 'base',     'token_symbol': 'TOSHI', 'contract_address': '0x2da56acd00b702c8f5a43d65f5fcbef7b3f3c36c',      'min_volume_usd': 200},
]


def _seed_hunt_targets():
    """Carga los targets por defecto en la BD si no existe ninguno."""
    from dashboard.models import WhaleHuntTarget
    if WhaleHuntTarget.objects.exists():
        return
    for t in _DEFAULT_HUNT_TARGETS:
        WhaleHuntTarget.objects.get_or_create(
            contract_address=t['contract_address'],
            blockchain=t['blockchain'],
            defaults={
                'token_symbol': t['token_symbol'],
                'min_volume_usd': t['min_volume_usd'],
                'is_active': True,
            }
        )
    logger.info("[WhaleHunter] Targets por defecto sembrados en la BD.")


@shared_task
def hunt_whales_by_pair_task(filter_high_volume=False, filter_recent_activity=False, filter_profitable=False, filter_min_volume=None, filter_min_tx_count=1):
    """
    Escanea los targets activos en WhaleHuntTarget (administrables desde el
    panel del dashboard) y añade automáticamente los mayores compradores.
    """
    from dashboard.models import WhaleWallet, WhaleHuntTarget
    from dashboard.services import PatternEngine

    # Semilla automática si la tabla está vacía
    _seed_hunt_targets()

    targets = WhaleHuntTarget.objects.filter(is_active=True)
    if not targets.exists():
        logger.warning("[WhaleHunter] No hay targets activos en la BD.")
        return {'new': 0, 'updated': 0, 'scanned': 0, 'total_buyers_found': 0, 'already_existed': 0, 'filtered_by_vol': 0, 'errors': []}

    total_new = 0
    total_updated = 0
    total_buyers_found = 0
    total_filtered_by_vol = 0
    total_filtered_by_tx = 0
    total_already_existed = 0
    scanned = 0
    errors = []

    for target in targets:
        blockchain = target.blockchain
        token_address = target.contract_address
        symbol = target.token_symbol
        min_vol = target.min_volume_usd
        # Aplicar filtro de volumen alto si está activo
        if filter_high_volume:
            min_vol = max(min_vol, 10000)  # mínimo $10,000
        # Sobrescribir volumen mínimo global si se especifica
        if filter_min_volume is not None:
            min_vol = max(min_vol, filter_min_volume)
        scanned += 1

        logger.info(f"[WhaleHunter] Escaneando ${symbol} ({blockchain}) → {token_address[:12]}...")

        try:
            top_buyers = PatternEngine.discover_token_whales(token_address, blockchain)
        except Exception as e:
            err_msg = f"${symbol}: {e}"
            logger.error(f"[WhaleHunter] Error escaneando {token_address[:12]}: {e}")
            errors.append(err_msg)
            continue

        if not top_buyers:
            logger.warning(f"[WhaleHunter] ${symbol}: API no devolvió compradores (pool no encontrado o sin trades).")
            errors.append(f"${symbol}: Sin datos de la API (pool no encontrado o 0 trades recientes)")
            continue

        total_buyers_found += len(top_buyers)
        max_vol_seen = max((b.get('volume', 0) for b in top_buyers), default=0)
        logger.info(f"[WhaleHunter] ${symbol}: {len(top_buyers)} compradores encontrados. Vol máx: ${max_vol_seen:,.2f}. Filtro mín: ${min_vol:,.0f}")

        for buyer in top_buyers:
            wallet_address = buyer.get('address', '')
            volume = buyer.get('volume', 0)

            if not wallet_address or volume < min_vol:
                if wallet_address:
                    total_filtered_by_vol += 1
                continue
            
            tx_count = buyer.get('tx_count', 0)
            if tx_count < filter_min_tx_count:
                total_filtered_by_tx += 1
                continue

            if blockchain in ['ethereum', 'base']:
                wallet_address = wallet_address.lower()

            try:
                whale, created = WhaleWallet.objects.get_or_create(
                    address=wallet_address,
                    blockchain=blockchain,
                    defaults={
                        'name': f'Hunter: {symbol} #{wallet_address[:6]}',
                        'wallet_category': 'OBSERVATION',
                        'filter_mode': 'OPEN',
                        'is_active': True,
                        'target_pairs': symbol,
                    }
                )
                if created:
                    total_new += 1
                    logger.info(f"[WhaleHunter] ✅ Nueva ballena de ${symbol}: {wallet_address[:10]} (vol: ${volume:,.0f})")
                    # Notificación Telegram
                    msg = (
                        f"🐋 <b>Nueva ballena descubierta</b>\n\n"
                        f"👤 <b>Address:</b> <code>{wallet_address[:10]}...</code>\n"
                        f"🌐 <b>Red:</b> {blockchain.upper()}\n"
                        f"🎯 <b>Token:</b> ${symbol}\n"
                        f"💰 <b>Volumen comprado:</b> ${volume:,.0f}\n"
                        f"📈 <b>Targets activos:</b> {symbol}\n\n"
                        f"<i>Ballena añadida automáticamente por el sistema de caza.</i>"
                    )
                    send_telegram_message(msg)
                    # Disparar sincronización inmediata en background
                    sync_wallet_task.delay(whale.id)
                else:
                    total_already_existed += 1
                    existing_pairs = whale.target_pairs or ''
                    if symbol.upper() not in [p.strip().upper() for p in existing_pairs.split(',')]:
                        whale.target_pairs = f"{existing_pairs},{symbol}" if existing_pairs else symbol
                        whale.save(update_fields=['target_pairs'])
                        total_updated += 1
                        # Disparar sincronización para capturar el nuevo par
                        sync_wallet_task.delay(whale.id)
            except Exception as e:
                logger.error(f"[WhaleHunter] Error creando wallet {wallet_address[:10]}: {e}")

    logger.info(f"[WhaleHunter] Caza completada: {total_new} nuevas, {total_updated} actualizadas, {total_buyers_found} compradores encontrados, {total_filtered_by_vol} filtrados por vol., {total_filtered_by_tx} filtrados por tx.")
    return {
        'new': total_new,
        'updated': total_updated,
        'scanned': scanned,
        'total_buyers_found': total_buyers_found,
        'already_existed': total_already_existed,
        'filtered_by_vol': total_filtered_by_vol,
        'filtered_by_tx': total_filtered_by_tx,
        'errors': errors,
    }


@shared_task
def analyze_wallet_task(wallet_id):
    """
    Tarea para analizar y categorizar automáticamente una wallet.
    """
    from dashboard.models import WhaleWallet
    from dashboard.services import PatternEngine
    
    try:
        wallet = WhaleWallet.objects.get(id=wallet_id)
        # Ejecutar análisis de patrones (esto ya incluye categorización)
        PatternEngine.analyze_wallet(wallet)
        logger.info(f"[AnalyzeWallet] Wallet {wallet.id} analizada y categorizada.")
    except Exception as e:
        logger.error(f"[AnalyzeWallet] Error analizando wallet {wallet_id}: {e}")


# ================================================================
# MÓDULO DE SCALPING — TAREAS CELERY
# ================================================================

@shared_task
def scan_scalping_pairs_task(timeframe='5m', top_n=15):
    """
    Escanea los pares de Binance y rankea las oportunidades de scalping.
    Guarda PairScanResult y crea ScalpAlerts para señales de alta confianza.
    Ejecutar cada 5 minutos via Celery Beat.
    """
    from dashboard.pair_scanner import scan_all_pairs, save_scan_results
    try:
        logger.info(f"[ScalpScanner] Iniciando escaneo {timeframe}...")
        results = scan_all_pairs(timeframe=timeframe, top_n=top_n, run_signals=True)
        if results:
            save_scan_results(results, timeframe=timeframe)
            logger.info(f"[ScalpScanner] {len(results)} pares analizados y guardados.")
        else:
            logger.warning("[ScalpScanner] No se obtuvieron resultados del scan.")
        return {'scanned': len(results), 'timeframe': timeframe}
    except Exception as e:
        logger.error(f"[ScalpScanner] Error en scan: {e}")
        return {'error': str(e)}


@shared_task
def run_scalping_bot_task(bot_id, force_eval=False):
    """
    Evalúa la estrategia de un ScalpingBot y ejecuta trade si hay señal.
    En modo simulado: crea ScalpingTrade en BD.
    En modo live: coloca orden real en Binance via CCXT.
    Ejecutar cada 1 minuto para cada bot activo.
    """
    from dashboard.models import ScalpingBot, ScalpingTrade, Pair
    from dashboard.pair_scanner import fetch_ohlcv_df, _get_exchange
    from dashboard.scalping_strategies import run_strategy
    from django.utils import timezone

    try:
        bot = ScalpingBot.objects.get(id=bot_id)
    except ScalpingBot.DoesNotExist:
        logger.error(f"[ScalpBot] Bot {bot_id} no existe.")
        return {'executed': False, 'reason': 'El bot no existe.'}

    if bot.status != 'RUNNING' and not force_eval:
        return {'executed': False, 'reason': 'El bot está PAUSADO o DETENIDO. Presiona Iniciar primero.'}


    # Verificar que no hay trade abierto ya
    open_trade = ScalpingTrade.objects.filter(bot=bot, status='OPEN').first()
    if open_trade:
        logger.debug(f"[ScalpBot] Bot {bot.name} tiene trade abierto, skip.")
        return {'executed': False, 'reason': 'Ya tiene un trade abierto activo.'}

    try:
        exchange = _get_exchange()
        if not exchange:
            raise Exception("No se pudo conectar a Binance.")

        symbol = bot.pair.symbol
        df = fetch_ohlcv_df(exchange, symbol, bot.timeframe, limit=250)
        if df is None or len(df) < 50:
            logger.warning(f"[ScalpBot] Datos insuficientes o error API temporal para {symbol}.")
            return {'executed': False, 'reason': f"Datos insuficientes o error API temporal para {symbol}."}

        result = run_strategy(
            bot.strategy_type, df,
            sl_atr_mult=float(bot.sl_atr_mult),
            tp_atr_mult=float(bot.tp_atr_mult),
            params=bot.parameters,
        )

        if not result['signal']:
            logger.debug(f"[ScalpBot] {bot.name}: sin señal.")
            return {'executed': False, 'reason': 'La estrategia (' + bot.strategy_type + ') evaluó el mercado pero NO encontró una señal fuerte de entrada en esta vela.'}

        signal    = result['signal']
        price     = result['entry']
        sl        = result['sl']
        tp        = result['tp']
        confidence= result['confidence']
        indicators= result['indicators']

        # Calcular cantidad
        capital   = float(bot.capital_usdt) * float(bot.max_position_pct) / 100
        quantity  = round(capital / price, 6)

        entry_order_id = None

        if bot.is_live:
            # ── MODO LIVE: colocar orden en Binance ──
            try:
                side_ccxt = 'buy' if signal == 'BUY' else 'sell'
                order = exchange.create_market_order(symbol, side_ccxt, quantity)
                entry_order_id = str(order.get('id', ''))
                price = float(order.get('price') or order.get('average') or price)
                logger.info(f"[ScalpBot LIVE] Orden {side_ccxt} {quantity} {symbol} @ {price} (ID: {entry_order_id})")
            except Exception as e:
                logger.error(f"[ScalpBot LIVE] Error colocando orden: {e}")
                bot.last_error = str(e)
                bot.status = 'ERROR'
                bot.save()
                return {'executed': False, 'reason': f'Error colocando orden: {str(e)}'}
        else:
            logger.info(f"[ScalpBot SIM] {signal} {quantity} {symbol} @ {price} | SL={sl} TP={tp} conf={confidence:.0%}")

        # Guardar trade
        ScalpingTrade.objects.create(
            bot                 = bot,
            side                = signal,
            entry_price         = price,
            stop_loss           = sl,
            take_profit         = tp,
            quantity            = quantity,
            status              = 'OPEN',
            entry_order_id      = entry_order_id,
            indicators_snapshot = indicators,
        )

        bot.total_trades += 1
        bot.save(update_fields=['total_trades', 'updated_at'])

        # Alerta Telegram
        mode_txt = '🔴 LIVE' if bot.is_live else '🟡 SIM'
        emoji = '🟢' if signal == 'BUY' else '🔴'
        msg = (
            f"{emoji} <b>Scalping {signal}</b> {mode_txt}\n\n"
            f"🤖 <b>Bot:</b> {bot.name}\n"
            f"📊 <b>Par:</b> {symbol} [{bot.timeframe}]\n"
            f"📈 <b>Estrategia:</b> {bot.get_strategy_type_display()}\n"
            f"💵 <b>Entrada:</b> <code>{price}</code>\n"
            f"🛑 <b>Stop Loss:</b> <code>{sl}</code>\n"
            f"🎯 <b>Take Profit:</b> <code>{tp}</code>\n"
            f"📦 <b>Cantidad:</b> {quantity}\n"
            f"🎲 <b>Confianza:</b> <code>{confidence:.0%}</code>"
        )
        send_telegram_message(msg)
        return {'executed': True, 'reason': f"Trade {signal} ejecutado correctamente a {price} USDT."}

    except Exception as e:
        logger.error(f"[ScalpBot] Bot {bot_id} error: {e}")
        try:
            bot.last_error = str(e)
            bot.status = 'ERROR'
            bot.save(update_fields=['last_error', 'status'])
        except Exception:
            pass
        return {'executed': False, 'reason': f"Error interno: {str(e)}"}


@shared_task
def check_scalping_positions_task():
    """
    Verifica SL/TP de todos los trades de scalping abiertos.
    En modo simulado: evalúa precio actual vs SL/TP.
    En modo live: coloca órdenes de cierre si se toca el nivel.
    Ejecutar cada 30 segundos.
    """
    from dashboard.models import ScalpingTrade, ScalpingBot
    from dashboard.pair_scanner import _get_exchange
    from django.utils import timezone

    open_trades = ScalpingTrade.objects.filter(status='OPEN').select_related('bot', 'bot__pair')
    if not open_trades.exists():
        return {'checked': 0}

    exchange = _get_exchange()
    if not exchange:
        logger.error("[ScalpPositions] No se pudo conectar a Binance.")
        return {'error': 'No exchange connection'}

    checked = 0
    closed  = 0

    for trade in open_trades:
        try:
            symbol = trade.bot.pair.symbol
            ticker = exchange.fetch_ticker(symbol)
            price  = float(ticker.get('last') or ticker.get('close', 0))
            if price <= 0:
                continue

            sl = float(trade.stop_loss)
            tp = float(trade.take_profit)
            ep = float(trade.entry_price)
            qty = float(trade.quantity)

            hit_tp = (trade.side == 'BUY'  and price >= tp) or (trade.side == 'SELL' and price <= tp)
            hit_sl = (trade.side == 'BUY'  and price <= sl) or (trade.side == 'SELL' and price >= sl)

            if not (hit_tp or hit_sl):
                checked += 1
                continue

            close_reason = 'CLOSED_TP' if hit_tp else 'CLOSED_SL'

            # Calcular PnL
            if trade.side == 'BUY':
                pnl_pct  = (price - ep) / ep * 100
                pnl_usdt = (price - ep) * qty
            else:
                pnl_pct  = (ep - price) / ep * 100
                pnl_usdt = (ep - price) * qty

            exit_order_id = None
            if trade.bot.is_live:
                try:
                    side_close = 'sell' if trade.side == 'BUY' else 'buy'
                    order = exchange.create_market_order(symbol, side_close, qty)
                    exit_order_id = str(order.get('id', ''))
                    price = float(order.get('price') or order.get('average') or price)
                except Exception as e:
                    logger.error(f"[ScalpPositions LIVE] Error cerrando {symbol}: {e}")

            # Actualizar trade
            trade.exit_price    = price
            trade.exit_time     = timezone.now()
            trade.status        = close_reason
            trade.pnl_usdt      = round(pnl_usdt, 4)
            trade.pnl_pct       = round(pnl_pct, 4)
            trade.exit_order_id = exit_order_id
            trade.save()

            # Actualizar estadísticas del bot
            bot = trade.bot
            bot.total_pnl_usdt += pnl_usdt
            if pnl_usdt > 0:
                bot.winning_trades += 1
            bot.save(update_fields=['total_pnl_usdt', 'winning_trades'])

            # Notificación Telegram
            emoji = '✅' if hit_tp else '❌'
            mode_txt = '🔴 LIVE' if bot.is_live else '🟡 SIM'
            msg = (
                f"{emoji} <b>Scalping CERRADO</b> {mode_txt}\n\n"
                f"🤖 <b>Bot:</b> {bot.name}\n"
                f"📊 <b>Par:</b> {symbol}\n"
                f"{'🎯 Take Profit alcanzado' if hit_tp else '🛑 Stop Loss tocado'}\n"
                f"💵 <b>Entrada:</b> <code>{ep}</code>\n"
                f"💵 <b>Salida:</b> <code>{price}</code>\n"
                f"{'📈' if pnl_usdt > 0 else '📉'} <b>PnL:</b> <code>{pnl_usdt:+.2f} USDT ({pnl_pct:+.2f}%)</code>"
            )
            send_telegram_message(msg)
            closed += 1

        except Exception as e:
            logger.error(f"[ScalpPositions] Error procesando trade {trade.id}: {e}")

    logger.info(f"[ScalpPositions] Chequeados: {checked + closed}, Cerrados: {closed}")
    return {'checked': checked, 'closed': closed}


@shared_task
def run_all_scalping_bots_task():
    """
    Encola la evaluación de todos los bots de scalping activos.
    Ejecutar cada 1 minuto via Celery Beat.
    """
    from dashboard.models import ScalpingBot
    bots = ScalpingBot.objects.filter(status='RUNNING')
    count = 0
    for bot in bots:
        run_scalping_bot_task.delay(bot.id)
        count += 1
    logger.info(f"[ScalpBots] {count} bots encolados.")
    return {'bots_queued': count}


# ================================================================
# MEJORAS CRÍTICAS: ENRIQUECIMIENTO RETROACTIVO + APRENDIZAJE
# ================================================================

@shared_task(bind=True, max_retries=2)
def retroactive_context_enrichment_task(self, wallet_id=None, timeframe='4h', limit_per_wallet=100):
    """
    Reconstruye el market_context histórico para transacciones que no lo tienen.

    El problema raíz: fetch_market_context() captura el estado del mercado en el
    momento del sync, NO en el momento real de la tx. Si una tx tiene 3 días de
    antigüedad, el contexto guardado es incorrecto (o inexistente si el sync fue
    posterior al trade).

    Esta tarea busca todas las txs de tipo BUY/SWAP sin market_context en raw_data
    y reconstruye los indicadores para el timestamp exacto de la transacción.

    Args:
        wallet_id: Si se especifica, procesa solo esa wallet. Si es None, procesa todas.
        timeframe: Temporalidad para los indicadores ('1h', '4h', '1d')
        limit_per_wallet: Máximo de txs a procesar por wallet (evita timeouts)

    Returns:
        dict con estadísticas del proceso
    """
    from dashboard.models import WhaleWallet, WhaleTransaction
    from dashboard.whale_intelligence import fetch_market_context_at
    import time as time_module

    logger.info(f"[RetroContext] Iniciando enriquecimiento retroactivo (wallet_id={wallet_id or 'TODAS'})")

    if wallet_id:
        wallets = WhaleWallet.objects.filter(id=wallet_id, is_active=True)
    else:
        wallets = WhaleWallet.objects.filter(is_active=True)

    total_enriched = 0
    total_skipped = 0
    total_failed = 0
    wallets_processed = 0

    for wallet in wallets:
        wallets_processed += 1

        txs_need_context = WhaleTransaction.objects.filter(
            wallet=wallet,
            tx_type__in=['BUY', 'SWAP', 'UNKNOWN'],
            to_asset__isnull=False,
        ).exclude(
            raw_data__market_context__isnull=False
        ).order_by('-timestamp')[:limit_per_wallet]

        if not txs_need_context.exists():
            logger.debug(f"[RetroContext] Wallet {wallet.address[:10]}: todas las txs ya tienen contexto.")
            continue

        tx_count = txs_need_context.count()
        logger.info(f"[RetroContext] Wallet {wallet.address[:10]}: {tx_count} txs sin contexto")

        enriched_this_wallet = 0
        for tx in txs_need_context:
            symbol = tx.to_asset
            if not symbol or symbol.upper() in ('USDC', 'USDT', 'DAI', 'BUSD', 'FDUSD'):
                total_skipped += 1
                continue

            try:
                timestamp_ms = int(tx.timestamp.timestamp() * 1000)
                ctx = fetch_market_context_at(symbol, timestamp_ms, timeframe=timeframe)

                if ctx:
                    raw = tx.raw_data or {}
                    raw['market_context'] = ctx
                    tx.raw_data = raw
                    tx.save(update_fields=['raw_data'])
                    enriched_this_wallet += 1
                    total_enriched += 1
                else:
                    total_skipped += 1

                time_module.sleep(0.3)

            except Exception as e:
                logger.warning(f"[RetroContext] Error enriqueciendo tx {tx.tx_hash[:16]} ({symbol}): {e}")
                total_failed += 1
                continue

        if enriched_this_wallet > 0:
            logger.info(f"[RetroContext] Wallet {wallet.address[:10]}: {enriched_this_wallet} txs enriquecidas.")

    _backfill_shadow_trade_context(timeframe=timeframe)

    summary = {
        'wallets_processed': wallets_processed,
        'txs_enriched': total_enriched,
        'txs_skipped_no_binance_pair': total_skipped,
        'txs_failed': total_failed,
    }
    logger.info(f"[RetroContext] Completado: {summary}")
    return summary


def _backfill_shadow_trade_context(timeframe='4h'):
    """
    Llena el market_context de ShadowTrades que no lo tienen,
    usando el timestamp de creacion del trade para reconstruir el contexto historico.
    """
    from dashboard.models import ShadowTrade
    from dashboard.whale_intelligence import fetch_market_context_at
    import time as time_module

    trades_no_ctx = ShadowTrade.objects.filter(market_context__isnull=True)[:200]
    filled = 0

    for trade in trades_no_ctx:
        try:
            symbol = trade.token_symbol
            if not symbol or symbol.upper() in ('USDC', 'USDT', 'DAI'):
                continue

            timestamp_ms = int(trade.created_at.timestamp() * 1000)
            ctx = fetch_market_context_at(symbol, timestamp_ms, timeframe=timeframe)
            if ctx:
                trade.market_context = ctx
                trade.save(update_fields=['market_context'])
                filled += 1

            time_module.sleep(0.3)
        except Exception:
            continue

    if filled > 0:
        logger.info(f"[RetroContext] ShadowTrades: {filled} contextos rellenados.")


@shared_task
def learn_whale_patterns_task(min_trades=3, min_win_rate=0.55):
    """
    Ejecuta el aprendizaje de patrones de ballenas con fuentes de datos ampliadas.

    Mejora critica #2: El WhalePatternLearner original solo usaba ShadowTrades
    cerrados con market_context. Esta tarea:
      1. Ejecuta el aprendizaje estandar (ShadowTrades cerrados)
      2. Anade aprendizaje directo desde WhaleTransactions enriquecidas
      3. Usa umbral reducido (min_trades=3 vs 5 anterior, min_win_rate=55% vs 60%)

    Returns:
        dict con resumen del aprendizaje
    """
    from dashboard.whale_pattern_learner import WhalePatternLearner
    from dashboard.models import WhaleTransaction, WhalePattern, ShadowTrade

    logger.info(f"[PatternLearner] Iniciando aprendizaje (min_trades={min_trades}, min_win_rate={min_win_rate})")

    standard_patterns = []
    try:
        standard_patterns = WhalePatternLearner.analyze_trades(
            min_trades=min_trades,
            min_win_rate=min_win_rate
        )
        logger.info(f"[PatternLearner] Paso 1: {len(standard_patterns)} patrones desde ShadowTrades cerrados.")
    except Exception as e:
        logger.warning(f"[PatternLearner] Error en aprendizaje estandar: {e}")

    extended_count = _learn_from_transactions(min_trades=min_trades, min_win_rate=min_win_rate)
    logger.info(f"[PatternLearner] Paso 2: {extended_count} patrones adicionales desde WhaleTransactions.")

    total_active = WhalePattern.objects.filter(is_active=True).count()
    shadow_closed = ShadowTrade.objects.filter(status='CLOSED', market_context__isnull=False).count()
    txs_with_ctx = WhaleTransaction.objects.filter(
        tx_type__in=['BUY', 'SWAP'],
        raw_data__market_context__isnull=False
    ).count()

    summary = {
        'patterns_from_shadow_trades': len(standard_patterns),
        'patterns_from_transactions': extended_count,
        'total_active_patterns': total_active,
        'dataset_shadow_trades_closed': shadow_closed,
        'dataset_txs_with_context': txs_with_ctx,
        'dataset_total': shadow_closed + txs_with_ctx,
    }
    logger.info(f"[PatternLearner] Completado: {summary}")
    return summary


def _learn_from_transactions(min_trades=3, min_win_rate=0.55):
    """
    Aprende patrones directamente de WhaleTransactions enriquecidas.
    Calcula PnL estimado usando precio de entrada en raw_data vs precio actual en Binance.
    Returns: numero de patrones nuevos o actualizados guardados.
    """
    from dashboard.models import WhaleTransaction
    from dashboard.whale_intelligence import fetch_market_context
    from dashboard.whale_pattern_learner import WhalePatternLearner
    import pandas as pd

    STABLES = {'USDC', 'USDT', 'DAI', 'BUSD', 'FDUSD'}
    txs = WhaleTransaction.objects.filter(
        tx_type__in=['BUY', 'SWAP'],
    ).exclude(to_asset__in=STABLES).filter(
        raw_data__market_context__isnull=False
    ).select_related('wallet').order_by('-timestamp')[:500]

    if not txs.exists():
        logger.info("[PatternLearner] Sin transacciones con contexto para aprendizaje extendido.")
        return 0

    data = []
    price_cache = {}

    for tx in txs:
        rd = tx.raw_data or {}
        ctx = rd.get('market_context', {})
        if not ctx:
            continue

        symbol = tx.to_asset
        if not symbol:
            continue

        entry_price = None
        try:
            if 'priceUsd' in rd:
                entry_price = float(rd['priceUsd'])
            elif 'px' in rd:
                entry_price = float(rd['px'])
        except Exception:
            pass

        if not entry_price or entry_price <= 0:
            continue

        if symbol not in price_cache:
            try:
                current_ctx = fetch_market_context(symbol)
                price_cache[symbol] = current_ctx.get('price') if current_ctx else None
            except Exception:
                price_cache[symbol] = None

        current_price = price_cache[symbol]
        if not current_price or current_price <= 0:
            continue

        pnl = ((current_price - entry_price) / entry_price) * 100

        row = {
            'trade_id': f"tx_{tx.id}",
            'symbol': symbol,
            'pnl': pnl,
            'win': 1 if pnl > 0 else 0,
            'wallet_id': tx.wallet_id,
        }
        for key, val in ctx.items():
            row[key] = val
        data.append(row)

    if len(data) < min_trades:
        logger.info(f"[PatternLearner] Dataset extendido insuficiente: {len(data)} filas (minimo {min_trades}).")
        return 0

    try:
        df = pd.DataFrame(data)

        for indicator, ranges in WhalePatternLearner.INDICATOR_RANGES.items():
            if indicator not in df.columns:
                continue
            df[f'{indicator}_range'] = df[indicator].apply(
                lambda x: WhalePatternLearner._get_range_label(x, ranges)
            )

        patterns = WhalePatternLearner._find_patterns(df, min_trades=min_trades, min_win_rate=min_win_rate)
        saved = WhalePatternLearner._save_patterns(patterns)
        return len(saved)

    except Exception as e:
        logger.error(f"[PatternLearner] Error en aprendizaje extendido: {e}")
        return 0
