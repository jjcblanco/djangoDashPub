from celery import shared_task
import logging

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
        if not wallet.is_active:
            return f"Wallet {wallet_id} is inactive."
            
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
        
        logger.info(f"Successfully synced {new_txs} txs for wallet {wallet_id} ({wallet.blockchain}).")
        return new_txs
    except Exception as e:
        logger.error(f"Error syncing wallet {wallet_id}: {str(e)}")
        raise e

@shared_task
def sync_all_whales_task():
    """
    Encola la sincronización de todas las ballenas activas.
    Ideal para ser llamado por Celery Beat o un Cronjob cada X minutos.
    """
    from dashboard.models import WhaleWallet
    active_wallets = WhaleWallet.objects.filter(is_active=True)
    count = 0
    for wallet in active_wallets:
        # Encolamos cada ballena de forma independiente para paralelizar
        sync_wallet_task.delay(wallet.id)
        count += 1
    
    logger.info(f"Queued background sync for {count} active whales.")
    return count
