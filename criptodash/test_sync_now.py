#!/usr/bin/env python3
"""
Test whale wallet sync immediately
Run: python test_sync_now.py
"""

import os
import sys
import time
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')
try:
    django.setup()
except Exception as e:
    print(f"❌ Django setup failed: {e}")
    sys.exit(1)

from dashboard.models import WhaleWallet, WhaleTransaction
from dashboard.tasks import sync_all_whales_task
from django.utils import timezone
from datetime import timedelta

def main():
    print("🔍 Testing Whale Wallet Sync System")
    print("=" * 60)
    
    # 1. Check pre-sync state
    print("\n📊 BEFORE sync:")
    wallets = WhaleWallet.objects.order_by('-last_sync')[:5]
    for w in wallets:
        if w.last_sync:
            mins = (timezone.now() - w.last_sync).total_seconds() / 60
            print(f"  Wallet {w.id} ({w.blockchain}): {mins:.1f} min ago")
        else:
            print(f"  Wallet {w.id} ({w.blockchain}): Never synced")
    
    total_wallets = WhaleWallet.objects.count()
    print(f"\n  Total wallets in system: {total_wallets}")
    
    # 2. Check recent transactions
    recent_txs_before = WhaleTransaction.objects.filter(
        timestamp__gte=timezone.now() - timedelta(minutes=10)
    ).count()
    print(f"  Transactions in last 10 min: {recent_txs_before}")
    
    # 3. Trigger sync
    print("\n🚀 Triggering sync_all_whales_task...")
    try:
        result = sync_all_whales_task.delay()
        print(f"  Task ID: {result.id}")
        print("  Task enqueued successfully")
    except Exception as e:
        print(f"❌ Failed to enqueue task: {e}")
        print("\n💡 Check if Celery is running:")
        print("  sudo systemctl status celery")
        sys.exit(1)
    
    # 4. Wait for tasks to process
    print("\n⏳ Waiting 60 seconds for tasks to execute...")
    for i in range(6):
        print(f"  {i*10} seconds...")
        time.sleep(10)
    
    # 5. Check post-sync state
    print("\n📊 AFTER sync:")
    wallets = WhaleWallet.objects.order_by('-last_sync')[:5]
    for w in wallets:
        if w.last_sync:
            mins = (timezone.now() - w.last_sync).total_seconds() / 60
            print(f"  Wallet {w.id} ({w.blockchain}): {mins:.1f} min ago")
        else:
            print(f"  Wallet {w.id} ({w.blockchain}): Still never synced")
    
    # 6. Check new transactions
    recent_txs_after = WhaleTransaction.objects.filter(
        timestamp__gte=timezone.now() - timedelta(minutes=2)
    ).count()
    print(f"\n📈 New transactions (last 2 minutes): {recent_txs_after}")
    
    # 7. Summary
    print("\n" + "=" * 60)
    print("📋 RESULTS:")
    
    if recent_txs_after > recent_txs_before:
        new_txs = recent_txs_after - recent_txs_before
        print(f"✅ SUCCESS: {new_txs} new transactions added!")
        print("   Wallets are syncing with V2 API.")
    elif recent_txs_after > 0:
        print(f"⚠️ Transactions exist but may be from earlier")
        print("   Check if timestamps are recent.")
    else:
        print("❌ FAILED: No new transactions added")
        print("\n💡 TROUBLESHOOTING:")
        print("1. Check Celery logs:")
        print("   sudo journalctl -u celery --since '2 minutes ago'")
        print("2. Look for 'synced X txs' or error messages")
        print("3. Check V2 API key:")
        print("   python -c \"import os; print('ETH_API_KEY:', 'SET' if os.environ.get('ETH_API_KEY') else 'NOT SET')\"")
        print("4. Test API directly:")
        print("   python test_v2_api.py")
    
    # 8. Additional diagnostics
    print("\n🔧 Additional diagnostics:")
    
    # Check sync status distribution
    from django.db.models import Count
    status_counts = WhaleWallet.objects.values('sync_status').annotate(count=Count('id'))
    print("  Wallet sync status:")
    for item in status_counts:
        print(f"    {item['sync_status']}: {item['count']}")
    
    # Check by blockchain
    blockchain_counts = WhaleWallet.objects.values('blockchain').annotate(count=Count('id'))
    print("  Wallets by blockchain:")
    for item in blockchain_counts:
        print(f"    {item['blockchain']}: {item['count']}")

if __name__ == '__main__':
    main()