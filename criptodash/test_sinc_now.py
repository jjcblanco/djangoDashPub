#!/usr/bin/env python3                                                                     Context                              █  
     import os, django, time                                                                    95.997 tokens                        █  
     os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')                     75% used                             █  
     django.setup()                                                                             $0.16 spent                          █  
                                                                                                                                     █  
     from dashboard.models import WhaleWallet, WhaleTransaction                                 LSP                                  █  
     from dashboard.tasks import sync_all_whales_task                                           LSPs will activate as files are read █  
     from django.utils import timezone                                                                                               █  
     from datetime import timedelta                                                             ▼ Modified Files                     █  
                                                                                                VPS_SECURITY_AUDIT_GUIDE.md       -1 █  
     print("🔍 Testing Sync System")                                                            criptodash/RUN_DIAGNOSTIC_VPS.md+264 █  
     print("="*60)                                                                              criptodash/UI_TEST_CHECKLIST.md +259 █  
                                                                                                criptodash/api_key_setup.py     +437    
     # 1. Check pre-sync state                                                                  criptodash/check_env.py         +121    
     print("\n📊 BEFORE sync:")                                                                 criptodash/configure_websockets.+322    
     wallets = WhaleWallet.objects.order_by('-last_sync')[:3]                                   criptodash/criptodash/asgi.py +11 -1    
     for w in wallets:                                                                          criptodash/criptodash/settings.py+14    
         if w.last_sync:                                                                        criptodash/dashboard/consumers.py+78    
             mins = (timezone.now() - w.last_sync).total_seconds() / 60                         criptodash/dashboard/routing.py   +6    
             print(f"  Wallet {w.id} ({w.blockchain}): {mins:.1f} min ago")                     criptodash/dashboard/services.p+3 -1    
         else:                                                                                  criptodash/dashboard/tasks.py +47 -2    
             print(f"  Wallet {w.id} ({w.blockchain}): Never")                                  criptodash/dashboard/template+919 -2    
                                                                                                criptodash/dashboard/urls.py      +2    
     # 2. Trigger sync  
      print("\n🚀 Triggering sync...")                                                           criptodash/RUN_DIAGNOSTIC_VPS.md+264 █  
     result = sync_all_whales_task.delay()                                                      criptodash/UI_TEST_CHECKLIST.md +259 █  
     print(f"  Task ID: {result.id}")                                                           criptodash/api_key_setup.py     +437    
                                                                                                criptodash/check_env.py         +121    
     # 3. Wait                                                                                  criptodash/configure_websockets.+322    
     print("⏳x Waiting 45 seconds...")                                                         criptodash/criptodash/asgi.py +11 -1    
     time.sleep(45)                                                                             criptodash/criptodash/settings.py+14    
                                                                                                criptodash/dashboard/consumers.py+78    
     # 4. Check post-sync                                                                       criptodash/dashboard/routing.py   +6    
     print("\n📊 AFTER sync:")                                                                  criptodash/dashboard/services.p+3 -1    
     wallets = WhaleWallet.objects.order_by('-last_sync')[:3]                                   criptodash/dashboard/tasks.py +47 -2    
     for w in wallets:                                                                          criptodash/dashboard/template+919 -2    
         if w.last_sync:                                                                        criptodash/dashboard/urls.py      +2    
             mins = (timezone.now() - w.last_sync).total_seconds() / 60                         criptodash/dashboard/views/__init_+3    
             print(f"  Wallet {w.id} ({w.blockchain}): {mins:.1f} min ago")                     criptodash/RUN_DIAGNOSTIC_VPS.md+264 █  
         else:                                                                                  criptodash/UI_TEST_CHECKLIST.md +259 █  
             print(f"  Wallet {w.id} ({w.blockchain}): Never")                                  criptodash/api_key_setup.py     +437    
                                                                                                criptodash/check_env.py         +121    
     # 5. Check new transactions                                                                criptodash/configure_websockets.+322    
     recent_txs = WhaleTransaction.objects.filter(                                              criptodash/criptodash/asgi.py +11 -1    
         timestamp__gte=timezone.now() - timedelta(minutes=2)                                   criptodash/criptodash/settings.py+14    
     ).count()                                                                                  criptodash/dashboard/consumers.py+78    
     print(f"\n📈 New transactions (last 2 min): {recent_txs}")                                 criptodash/dashboard/routing.py   +6    
                                                                                                criptodash/dashboard/services.p+3 -1    
     if recent_txs > 0:                                                                         criptodash/dashboard/tasks.py +47 -2    
         print("\n✅t SUCCESS: Wallets are syncing!")                                           criptodash/dashboard/template+919 -2    
     else:                                                                                      criptodash/dashboard/urls.py      +2    
         print("\n❌  FAILED: No new transactions")
         print("\n💡 Check:")                                                                   criptodash/RUN_DIAGNOSTIC_VPS.md+264 █  
         print("  1. Celery logs: sudo journalctl -u celery --since '1 minute ago'")            criptodash/UI_TEST_CHECKLIST.md +259 █  
         print("  2. V2 API key: python -c \"import os; print('ETH_API_KEY:', 'SET' if os.criptodash/api_key_setup.py environ.get('ETH_API_KEY') else 'NOT SET')\"")