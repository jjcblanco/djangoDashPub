#!/usr/bin/env python3
"""
Comprehensive Whale Tracking Diagnostic Script
Run: python whale_diagnostic.py [OPTIONS]

Options:
  --status       : Show wallet sync status (default)
  --blockchain   : Show stats by blockchain
  --problematic  : Show only problematic wallets
  --transactions : Show recent transaction counts
  --fix-stuck    : Reset stuck SYNCING wallets
  --api-check    : Check API configurations
  --rate-limits  : Check rate limit configurations
  --celery-status: Check Celery worker and beat status
  --ui-check     : Check UI endpoints accessibility
  --all          : Run all diagnostics
"""

import os
import sys
import django
from datetime import datetime, timedelta
import argparse

# Setup Django environment
def setup_django():
    """Configure Django settings based on environment"""
    # Try to find project root
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = script_dir
    
    # Check if we're in the correct directory
    if not os.path.exists(os.path.join(project_root, 'manage.py')):
        print(f"❌ Error: Could not find manage.py in {project_root}")
        print("Please run this script from the Django project root directory.")
        sys.exit(1)
    
    # Add project to path and setup Django
    sys.path.insert(0, project_root)
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')
    
    try:
        django.setup()
        print(f"✅ Django setup complete (project: {project_root})")
        return True
    except Exception as e:
        print(f"❌ Django setup failed: {e}")
        return False

def check_wallet_status():
    """Check sync status of all wallets"""
    from dashboard.models import WhaleWallet
    
    print("\n" + "="*60)
    print("WALLET SYNC STATUS REPORT")
    print("="*60)
    
    wallets = WhaleWallet.objects.all()
    active_wallets = wallets.filter(is_active=True)
    
    print(f"📊 Total Wallets: {wallets.count()}")
    print(f"✅ Active Wallets: {active_wallets.count()}")
    
    # Status breakdown
    print("\n📈 STATUS BREAKDOWN:")
    for status in ['IDLE', 'SYNCING', 'ERROR']:
        count = wallets.filter(sync_status=status).count()
        percentage = (count / wallets.count() * 100) if wallets.count() > 0 else 0
        print(f"  {status}: {count} ({percentage:.1f}%)")
    
    # Last sync analysis
    print("\n🕒 LAST SYNC ANALYSIS:")
    now = django.utils.timezone.now()
    time_frames = [
        ('<1 hour', timedelta(hours=1)),
        ('1-6 hours', timedelta(hours=6)),
        ('6-24 hours', timedelta(hours=24)),
        ('>24 hours', timedelta(days=1))
    ]
    
    for label, delta in time_frames:
        if label == '<1 hour':
            recent = wallets.filter(last_sync__gte=now - delta).count()
        elif label == '1-6 hours':
            recent = wallets.filter(
                last_sync__lt=now - timedelta(hours=1),
                last_sync__gte=now - delta
            ).count()
        elif label == '6-24 hours':
            recent = wallets.filter(
                last_sync__lt=now - timedelta(hours=6),
                last_sync__gte=now - delta
            ).count()
        else:  # >24 hours
            recent = wallets.filter(last_sync__lt=now - delta).count()
        
        print(f"  {label}: {recent} wallets")
    
    never_synced = wallets.filter(last_sync__isnull=True).count()
    print(f"  Never synced: {never_synced} wallets")
    
    return wallets

def check_by_blockchain():
    """Analyze wallets by blockchain"""
    from dashboard.models import WhaleWallet
    from django.utils import timezone
    
    print("\n" + "="*60)
    print("BLOCKCHAIN ANALYSIS")
    print("="*60)
    
    blockchains = ['solana', 'ethereum', 'base', 'hyperliquid']
    
    for bc in blockchains:
        bc_wallets = WhaleWallet.objects.filter(blockchain=bc)
        if not bc_wallets.exists():
            print(f"\n{bc.upper()}: No wallets")
            continue
            
        active = bc_wallets.filter(is_active=True)
        latest = active.order_by('-last_sync').first()
        
        print(f"\n{bc.upper()}:")
        print(f"  Total: {bc_wallets.count()}")
        print(f"  Active: {active.count()}")
        
        # Status breakdown
        for status in ['IDLE', 'SYNCING', 'ERROR']:
            cnt = bc_wallets.filter(sync_status=status).count()
            if cnt > 0:
                print(f"  {status}: {cnt}")
        
        if latest and latest.last_sync:
            hours_ago = (timezone.now() - latest.last_sync).total_seconds() / 3600
            print(f"  Latest sync: {latest.last_sync} ({hours_ago:.1f} hours ago)")
        else:
            print(f"  Latest sync: Never")
        
        # Show sample wallet
        sample = bc_wallets.first()
        print(f"  Sample: ID {sample.id} - {sample.address[:12]}...")

def show_problematic_wallets():
    """Show wallets with issues"""
    from dashboard.models import WhaleWallet
    from django.utils import timezone
    
    print("\n" + "="*60)
    print("PROBLEMATIC WALLETS")
    print("="*60)
    
    # 1. Wallets with ERROR status
    error_wallets = WhaleWallet.objects.filter(sync_status='ERROR')
    if error_wallets.exists():
        print("\n❌ WALLETS WITH ERROR STATUS:")
        for w in error_wallets[:10]:  # Limit to 10
            print(f"  ID {w.id}: {w.address[:12]}... ({w.blockchain}) - Last: {w.last_sync}")
        if error_wallets.count() > 10:
            print(f"  ... and {error_wallets.count() - 10} more")
    else:
        print("\n✅ No wallets with ERROR status")
    
    # 2. Wallets stuck in SYNCING (>30 minutes)
    cutoff = timezone.now() - timedelta(minutes=30)
    stuck_wallets = WhaleWallet.objects.filter(
        sync_status='SYNCING',
        last_sync__lt=cutoff
    )
    
    if stuck_wallets.exists():
        print(f"\n⚠️ WALLETS STUCK IN SYNCING (>30 min): {stuck_wallets.count()}")
        for w in stuck_wallets[:10]:
            hours_stuck = (timezone.now() - w.last_sync).total_seconds() / 3600 if w.last_sync else 999
            print(f"  ID {w.id}: {w.address[:12]}... ({w.blockchain}) - Stuck for {hours_stuck:.1f}h")
        if stuck_wallets.count() > 10:
            print(f"  ... and {stuck_wallets.count() - 10} more")
    else:
        print("\n✅ No wallets stuck in SYNCING")
    
    # 3. Inactive wallets
    inactive = WhaleWallet.objects.filter(is_active=False)
    if inactive.exists():
        print(f"\n🚫 INACTIVE WALLETS: {inactive.count()}")
        for w in inactive[:5]:
            print(f"  ID {w.id}: {w.address[:12]}... ({w.blockchain}) - Status: {w.sync_status}")
    
    # 4. Never synced
    never_synced = WhaleWallet.objects.filter(last_sync__isnull=True, is_active=True)
    if never_synced.exists():
        print(f"\n🕒 NEVER SYNCED (Active): {never_synced.count()}")
        for w in never_synced[:5]:
            print(f"  ID {w.id}: {w.address[:12]}... ({w.blockchain})")

def check_transaction_counts():
    """Check recent transaction activity"""
    from dashboard.models import WhaleTransaction
    from django.utils import timezone
    
    print("\n" + "="*60)
    print("TRANSACTION ACTIVITY")
    print("="*60)
    
    now = timezone.now()
    time_periods = [
        ('Last 1 hour', timedelta(hours=1)),
        ('Last 6 hours', timedelta(hours=6)),
        ('Last 24 hours', timedelta(hours=24)),
        ('Last 7 days', timedelta(days=7)),
    ]
    
    for label, delta in time_periods:
        cutoff = now - delta
        count = WhaleTransaction.objects.filter(timestamp__gte=cutoff).count()
        print(f"  {label}: {count} transactions")
    
    # Transactions by type (last 24h)
    cutoff_24h = now - timedelta(hours=24)
    txs_24h = WhaleTransaction.objects.filter(timestamp__gte=cutoff_24h)
    
    if txs_24h.exists():
        print("\n📊 TRANSACTION TYPES (Last 24h):")
        from django.db.models import Count
        by_type = txs_24h.values('tx_type').annotate(count=Count('id')).order_by('-count')
        for item in by_type:
            print(f"  {item['tx_type'] or 'UNKNOWN'}: {item['count']}")

def fix_stuck_wallets():
    """Reset wallets stuck in SYNCING state"""
    from dashboard.models import WhaleWallet
    from django.utils import timezone
    
    print("\n" + "="*60)
    print("FIXING STUCK WALLETS")
    print("="*60)
    
    cutoff = timezone.now() - timedelta(minutes=30)
    stuck_wallets = WhaleWallet.objects.filter(
        sync_status='SYNCING',
        last_sync__lt=cutoff
    )
    
    if not stuck_wallets.exists():
        print("✅ No wallets stuck in SYNCING state")
        return
    
    print(f"Found {stuck_wallets.count()} wallets stuck in SYNCING")
    print("\nResetting to IDLE state...")
    
    updated = stuck_wallets.update(sync_status='IDLE')
    print(f"✅ Reset {updated} wallets to IDLE state")
    
    # Show which ones were fixed
    for w in stuck_wallets[:5]:
        print(f"  Fixed ID {w.id}: {w.address[:12]}... ({w.blockchain})")

def check_api_configurations():
    """Check API key configurations"""
    import os
    
    print("\n" + "="*60)
    print("API CONFIGURATION CHECK")
    print("="*60)
    
    # Check environment variables
    api_keys = {
        'ETH_API_KEY': 'Etherscan API Key (Ethereum)',
        'BASE_API_KEY': 'Basescan API Key (Base)',
        'BINANCE_APIKEY': 'Binance API Key',
        'BINANCE_SECRET': 'Binance Secret',
        'TELEGRAM_BOT_TOKEN': 'Telegram Bot Token',
        'TELEGRAM_CHAT_ID': 'Telegram Chat ID',
    }
    
    print("🔑 API KEYS STATUS:")
    for key, description in api_keys.items():
        value = os.environ.get(key)
        if value:
            # Don't show full key, just indication
            masked = value[:8] + '...' if len(value) > 8 else '***'
            print(f"  ✅ {description}: Configured ({masked})")
        else:
            print(f"  ❌ {description}: MISSING")
    
    # Check from Django settings
    try:
        from django.conf import settings
        print("\n⚙️ DJANGO SETTINGS CHECK:")
        
        # Check Celery config
        celery_broker = getattr(settings, 'CELERY_BROKER_URL', 'Not set')
        print(f"  Celery Broker: {celery_broker[:50]}..." if len(celery_broker) > 50 else f"  Celery Broker: {celery_broker}")
        print(f"  Redis available: {'redis' in celery_broker.lower()}")
        
        # Check installed apps
        if 'channels' in getattr(settings, 'INSTALLED_APPS', []):
            print(f"  Django Channels: ✅ Installed")
        else:
            print(f"  Django Channels: ⚠️ Not in INSTALLED_APPS")
            
        # Check if WebSocket routing is configured
        if hasattr(settings, 'ASGI_APPLICATION'):
            print(f"  ASGI Application: {settings.ASGI_APPLICATION}")
        else:
            print(f"  ASGI Application: ⚠️ Not configured")
            
    except Exception as e:
        print(f"  Error checking settings: {e}")

def check_rate_limits():
    """Check rate limit configurations"""
    print("\n" + "="*60)
    print("RATE LIMIT CONFIGURATION")
    print("="*60)
    
    try:
        from dashboard.utils.blockchain import get_api_client
        from dashboard.utils.rate_limiter import RateLimiter
        
        print("📊 RATE LIMITER STATUS:")
        
        # Check if rate limiter module exists
        try:
            import importlib
            rate_limiter_spec = importlib.util.find_spec("dashboard.utils.rate_limiter")
            if rate_limiter_spec:
                print("  RateLimiter module: ✅ Found")
            else:
                print("  RateLimiter module: ⚠️ Not found")
        except:
            print("  RateLimiter module: ❌ Error checking")
        
        # Check common blockchain API clients
        blockchains = ['ethereum', 'base', 'solana', 'hyperliquid']
        
        for bc in blockchains:
            try:
                # Try to get API client for each blockchain
                client = get_api_client(bc)
                if client:
                    print(f"  {bc.upper()} API Client: ✅ Available")
                else:
                    print(f"  {bc.upper()} API Client: ⚠️ Not configured")
            except Exception as e:
                print(f"  {bc.upper()} API Client: ❌ Error - {str(e)[:50]}")
                
    except ImportError as e:
        print(f"  ❌ Could not import blockchain utilities: {e}")
    except Exception as e:
        print(f"  ❌ Error checking rate limits: {e}")

def check_celery_status():
    """Check Celery worker and beat status"""
    print("\n" + "="*60)
    print("CELERY STATUS CHECK")
    print("="*60)
    
    try:
        from django.conf import settings
        from celery import current_app
        
        print("👷 CELERY CONFIGURATION:")
        
        # Check if Celery app is configured
        try:
            app = current_app
            print(f"  Celery App: ✅ Configured")
            
            # Check registered tasks
            registered_tasks = list(app.tasks.keys())
            whale_tasks = [t for t in registered_tasks if 'whale' in t.lower() or 'sync' in t.lower()]
            
            print(f"  Total registered tasks: {len(registered_tasks)}")
            print(f"  Whale-related tasks: {len(whale_tasks)}")
            
            if whale_tasks:
                print("  Found whale tasks:")
                for task in whale_tasks[:3]:  # Show first 3
                    print(f"    - {task}")
                if len(whale_tasks) > 3:
                    print(f"    ... and {len(whale_tasks) - 3} more")
            
        except Exception as e:
            print(f"  Celery App: ❌ Error - {e}")
        
        # Check Celery Beat schedule
        print("\n⏰ CELERY BEAT SCHEDULE:")
        beat_schedule = getattr(settings, 'CELERY_BEAT_SCHEDULE', {})
        
        if beat_schedule:
            print(f"  Scheduled tasks: {len(beat_schedule)}")
            for task_name, config in beat_schedule.items():
                if 'whale' in task_name.lower() or 'hunt' in task_name.lower() or 'sync' in task_name.lower():
                    schedule = config.get('schedule', 'Unknown')
                    print(f"    ✅ {task_name}: {schedule}")
        else:
            print("  ⚠️ No Celery Beat schedule configured")
            
    except Exception as e:
        print(f"  ❌ Error checking Celery status: {e}")

def check_ui_endpoints():
    """Check if UI endpoints are accessible"""
    print("\n" + "="*60)
    print("UI ENDPOINTS CHECK")
    print("="*60)
    
    try:
        from django.test import Client
        from django.urls import reverse
        
        client = Client()
        endpoints = [
            ('whale_insights', 'Whale Insights Dashboard'),
            ('whale_wallet_list', 'Wallet List API'),
            ('whale_hunt_targets', 'Hunt Targets API'),
            ('consensus_signals', 'Consensus Signals API'),
        ]
        
        print("🌐 ENDPOINT AVAILABILITY:")
        
        for url_name, description in endpoints:
            try:
                url = reverse(url_name)
                response = client.get(url)
                
                if response.status_code == 200:
                    print(f"  ✅ {description}: HTTP {response.status_code} ({url})")
                elif response.status_code == 302:  # Redirect (login required)
                    print(f"  ⚠️ {description}: HTTP {response.status_code} - Login required ({url})")
                else:
                    print(f"  ❌ {description}: HTTP {response.status_code} ({url})")
                    
            except Exception as e:
                print(f"  ❌ {description}: Error - {str(e)[:50]}")
                
        # Check WebSocket endpoint
        print("\n🔌 WEBSOCKET ENDPOINTS:")
        try:
            from django.urls import get_resolver
            resolver = get_resolver()
            
            # Look for WebSocket patterns
            ws_patterns = []
            for pattern in resolver.url_patterns:
                if hasattr(pattern, 'pattern'):
                    pattern_str = str(pattern.pattern)
                    if 'ws' in pattern_str.lower() or 'websocket' in pattern_str.lower():
                        ws_patterns.append(pattern_str)
            
            if ws_patterns:
                print(f"  Found WebSocket patterns: {len(ws_patterns)}")
                for pattern in ws_patterns[:2]:
                    print(f"    - {pattern}")
            else:
                print(f"  ⚠️ No WebSocket patterns found")
                
        except Exception as e:
            print(f"  ❌ Error checking WebSocket patterns: {e}")
            
    except Exception as e:
        print(f"  ❌ Error checking UI endpoints: {e}")

def run_all_diagnostics():
    """Run all diagnostic checks"""
    print("🔍 RUNNING COMPREHENSIVE WHALE TRACKING DIAGNOSTICS")
    print("="*60)
    
    wallets = check_wallet_status()
    check_by_blockchain()
    show_problematic_wallets()
    check_transaction_counts()
    check_api_configurations()
    check_rate_limits()
    check_celery_status()
    check_ui_endpoints()
    
    print("\n" + "="*60)
    print("DIAGNOSTICS COMPLETE")
    print("="*60)

def main():
    parser = argparse.ArgumentParser(description='Whale Tracking Diagnostic Tool')
    parser.add_argument('--status', action='store_true', help='Show wallet sync status')
    parser.add_argument('--blockchain', action='store_true', help='Show stats by blockchain')
    parser.add_argument('--problematic', action='store_true', help='Show only problematic wallets')
    parser.add_argument('--transactions', action='store_true', help='Show recent transaction counts')
    parser.add_argument('--fix-stuck', action='store_true', help='Reset stuck SYNCING wallets')
    parser.add_argument('--api-check', action='store_true', help='Check API configurations')
    parser.add_argument('--rate-limits', action='store_true', help='Check rate limit configurations')
    parser.add_argument('--celery-status', action='store_true', help='Check Celery worker and beat status')
    parser.add_argument('--ui-check', action='store_true', help='Check UI endpoints accessibility')
    parser.add_argument('--all', action='store_true', help='Run all diagnostics')
    
    args = parser.parse_args()
    
    # Setup Django
    if not setup_django():
        return
    
    # Run diagnostics based on arguments
    if args.all:
        run_all_diagnostics()
    elif args.fix_stuck:
        fix_stuck_wallets()
    elif args.blockchain:
        check_by_blockchain()
    elif args.problematic:
        show_problematic_wallets()
    elif args.transactions:
        check_transaction_counts()
    elif args.api_check:
        check_api_configurations()
    elif args.rate_limits:
        check_rate_limits()
    elif args.celery_status:
        check_celery_status()
    elif args.ui_check:
        check_ui_endpoints()
    else:
        # Default: show status
        check_wallet_status()

if __name__ == '__main__':
    main()