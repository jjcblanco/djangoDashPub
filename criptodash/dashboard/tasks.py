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
