#!/usr/bin/env python3
""" 
Diagnose Django URL configuration errors in Celery
Run: python diagnose_celery_django.py
"""

import os
import sys
import django
from pathlib import Path

def setup_django():
    """Configure Django environment"""
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir
    
    if not os.path.exists(os.path.join(project_root, 'manage.py')):
        print(f"❌ Error: Could not find manage.py in {project_root}")
        return False
    
    sys.path.insert(0, project_root)
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')
    
    try:
        django.setup()
        print(f"✅ Django setup complete")
        return True
    except Exception as e:
        print(f"❌ Django setup failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_urls():
    """Check URL configuration"""
    print("\n🔍 Checking URL configuration...")
    
    try:
        from django.urls import get_resolver, reverse, NoReverseMatch
        from django.conf import settings
        
        resolver = get_resolver()
        
        print(f"URL Patterns found: {len(resolver.url_patterns)}")
        
        # Check for common URL patterns
        expected_urls = [
            'admin:index',
            'whale_insights',
            'whale_wallet_list',
            'whale_hunt_targets',
        ]
        
        print("\n🔗 Testing URL reversals:")
        for url_name in expected_urls:
            try:
                url = reverse(url_name)
                print(f"  ✅ {url_name}: {url}")
            except NoReverseMatch:
                print(f"  ❌ {url_name}: Not found")
            except Exception as e:
                print(f"  ⚠️ {url_name}: Error - {e}")
        
        # Check installed apps
        print(f"\n📱 Installed Apps ({len(settings.INSTALLED_APPS)}):")
        for app in settings.INSTALLED_APPS:
            if 'dashboard' in app or 'channels' in app:
                print(f"  ✅ {app}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error checking URLs: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_evm_tracker():
    """Check if EVMWhaleTracker is properly configured"""
    print("\n🔍 Checking EVMWhaleTracker V2 API...")
    
    try:
        from dashboard.services import EVMWhaleTracker
        
        # Test Ethereum tracker
        print("Testing Ethereum tracker...")
        eth_tracker = EVMWhaleTracker('ethereum')
        print(f"  API URL: {eth_tracker.api_url}")
        print(f"  Has API key: {'Yes' if eth_tracker.api_key else 'No'}")
        
        # Check if URL contains /v2
        if '/v2' in eth_tracker.api_url:
            print(f"  ✅ V2 API endpoint: {eth_tracker.api_url}")
        else:
            print(f"  ❌ NOT V2 API: {eth_tracker.api_url}")
        
        # Test Base tracker
        print("\nTesting Base tracker...")
        try:
            base_tracker = EVMWhaleTracker('base')
            print(f"  API URL: {base_tracker.api_url}")
            print(f"  Has API key: {'Yes' if base_tracker.api_key else 'No'}")
            if '/v2' in base_tracker.api_url:
                print(f"  ✅ V2 API endpoint: {base_tracker.api_url}")
            else:
                print(f"  ❌ NOT V2 API: {base_tracker.api_url}")
        except Exception as e:
            print(f"  ⚠️ Base tracker error: {e}")
        
        return True
        
    except ImportError as e:
        print(f"❌ Could not import EVMWhaleTracker: {e}")
        return False
    except Exception as e:
        print(f"❌ Error checking EVMWhaleTracker: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_celery_config():
    """Check Celery configuration"""
    print("\n🔍 Checking Celery configuration...")
    
    try:
        from django.conf import settings
        
        # Check broker
        broker = getattr(settings, 'CELERY_BROKER_URL', 'Not set')
        print(f"  Celery Broker: {broker}")
        
        # Check beat schedule
        beat_schedule = getattr(settings, 'CELERY_BEAT_SCHEDULE', {})
        print(f"  Beat Schedule tasks: {len(beat_schedule)}")
        
        for task_name, config in beat_schedule.items():
            schedule = config.get('schedule', 'Unknown')
            print(f"    - {task_name}: {schedule}")
        
        # Check if celery.py exists
        celery_path = os.path.join(Path(__file__).resolve().parent, 'criptodash', 'celery.py')
        if os.path.exists(celery_path):
            print(f"  ✅ celery.py exists: {celery_path}")
        else:
            print(f"  ❌ celery.py not found")
        
        return True
        
    except Exception as e:
        print(f"❌ Error checking Celery config: {e}")
        return False

def test_sync_task():
    """Test if sync task can be created"""
    print("\n🔍 Testing sync task creation...")
    
    try:
        from dashboard.tasks import sync_all_whales_task
        
        print(f"  Task function: {sync_all_whales_task}")
        print(f"  Task name: {sync_all_whales_task.name}")
        
        # Try to delay the task (won't execute without Celery worker)
        from celery import current_app
        app = current_app
        
        print(f"  Celery app: {app}")
        
        # Check if task is registered
        registered_tasks = list(app.tasks.keys())
        whale_tasks = [t for t in registered_tasks if 'whale' in t.lower() or 'sync' in t.lower()]
        
        print(f"  Total registered tasks: {len(registered_tasks)}")
        print(f"  Whale-related tasks: {len(whale_tasks)}")
        
        if 'dashboard.tasks.sync_all_whales_task' in registered_tasks:
            print(f"  ✅ sync_all_whales_task is registered")
        else:
            print(f"  ❌ sync_all_whales_task NOT registered")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing sync task: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_for_url_errors():
    """Specifically check for URL-related errors"""
    print("\n🔍 Checking for URL configuration errors...")
    
    try:
        # Try to import URL patterns
        from dashboard import urls as dashboard_urls
        
        print(f"  Dashboard URL patterns: {len(dashboard_urls.urlpatterns)}")
        
        # Check each pattern
        for i, pattern in enumerate(dashboard_urls.urlpatterns[:5]):
            print(f"    Pattern {i}: {pattern}")
        
        # Check for recursive imports
        print(f"\n🔍 Checking for circular imports...")
        
        # Try to import views that might cause issues
        try:
            from dashboard.views import whale_views
            print(f"  ✅ whale_views imports OK")
        except Exception as e:
            print(f"  ❌ whale_views import error: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ URL check error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("🔧 Diagnosing Django/Celery Configuration Issues")
    print("="*60)
    
    # Setup Django first
    if not setup_django():
        print("\n❌ Django setup failed. This is likely the Celery error.")
        print("\n💡 Solutions:")
        print("1. Check URL patterns in dashboard/urls.py")
        print("2. Check for circular imports in dashboard/views/")
        print("3. Verify INSTALLED_APPS includes 'dashboard'")
        print("4. Check Django settings for errors")
        return
    
    # Run checks
    check_urls()
    check_evm_tracker()
    check_celery_config()
    test_sync_task()
    check_for_url_errors()
    
    print("\n" + "="*60)
    print("📋 SUMMARY:")
    print("\nIf Celery is failing with URL errors:")
    print("1. Restart Celery with debug logging:")
    print("   sudo systemctl restart celery")
    print("   sudo journalctl -u celery -f")
    print("\n2. Check for specific error in logs")
    print("3. If 'url_patterns' error, check dashboard/urls.py")
    print("4. Ensure all views import correctly")
    
    print("\n🚀 Quick fix attempt:")
    print("   python manage.py check --deploy")
    print("   python manage.py test dashboard")

if __name__ == '__main__':
    main()