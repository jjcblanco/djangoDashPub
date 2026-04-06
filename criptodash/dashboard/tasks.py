from celery import shared_task
import logging
from django.utils import timezone

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
    count = 0
    for wallet in active_wallets:
        sync_wallet_task.delay(wallet.id)
        count += 1
    
    logger.info(f"Encolada sincronización en background para {count} ballenas activas.")
    return count


# ───────────────────────────────────────────
# HUNTER DE BALLENAS POR PAR / TOKEN
# ───────────────────────────────────────────

# Targets por defecto usados como semilla si la BD está vacía
_DEFAULT_HUNT_TARGETS = [
    {'blockchain': 'solana',   'token_symbol': 'WIF',   'contract_address': 'EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm', 'min_volume_usd': 3000},
    {'blockchain': 'solana',   'token_symbol': 'BONK',  'contract_address': 'DezXAZ8z7Pnrn9vzctrxEXpWMrNHqR1f6f69nL4XYUDx', 'min_volume_usd': 2000},
    {'blockchain': 'solana',   'token_symbol': 'JUP',   'contract_address': 'JUPyiPZp718zay7kaPn2CoJvRwvpqcRuS5B7shuYf79',  'min_volume_usd': 5000},
    {'blockchain': 'ethereum', 'token_symbol': 'PEPE',  'contract_address': '0x6982508145454ce325ddbe47a25d4ec3d2311933',      'min_volume_usd': 5000},
    {'blockchain': 'ethereum', 'token_symbol': 'SHIB',  'contract_address': '0x95aD61b0a150d79219dCF64E1E6Cc01f0B64C4cE',      'min_volume_usd': 5000},
    {'blockchain': 'base',     'token_symbol': 'TOSHI', 'contract_address': '0x2da56acd00b702c8f5a43d65f5fcbef7b3f3c36c',      'min_volume_usd': 2000},
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
def hunt_whales_by_pair_task():
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
        return {'new': 0, 'updated': 0}

    total_new = 0
    total_updated = 0

    for target in targets:
        blockchain = target.blockchain
        token_address = target.contract_address
        symbol = target.token_symbol
        min_vol = target.min_volume_usd

        logger.info(f"[WhaleHunter] Escaneando ${symbol} ({blockchain}) → {token_address[:12]}...")

        try:
            top_buyers = PatternEngine.discover_token_whales(token_address, blockchain)
        except Exception as e:
            logger.error(f"[WhaleHunter] Error escaneando {token_address[:12]}: {e}")
            continue

        for buyer in top_buyers:
            wallet_address = buyer.get('address', '')
            volume = buyer.get('volume', 0)

            if not wallet_address or volume < min_vol:
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
                else:
                    existing_pairs = whale.target_pairs or ''
                    if symbol.upper() not in [p.strip().upper() for p in existing_pairs.split(',')]:
                        whale.target_pairs = f"{existing_pairs},{symbol}" if existing_pairs else symbol
                        whale.save(update_fields=['target_pairs'])
                        total_updated += 1
            except Exception as e:
                logger.error(f"[WhaleHunter] Error creando wallet {wallet_address[:10]}: {e}")

    logger.info(f"[WhaleHunter] Caza completada: {total_new} nuevas, {total_updated} actualizadas.")
    return {'new': total_new, 'updated': total_updated}

