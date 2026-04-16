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

