#!/usr/bin/env python3
"""
Patch EVMWhaleTracker to log API errors for debugging
Run this on VPS to add error logging
"""

import os

def patch_evm_tracker():
    """Add error logging to EVMWhaleTracker.sync_wallet method"""
    file_path = os.path.join(os.path.dirname(__file__), 'dashboard', 'services.py')
    
    if not os.path.exists(file_path):
        print(f"❌ File not found: {file_path}")
        return False
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Find the sync_wallet method in EVMWhaleTracker
    target_line = 'if data.get(\'status\') != \'1\': return 0'
    
    if target_line not in content:
        print(f"❌ Could not find target line: {target_line}")
        return False
    
    # Replace with version that logs error
    new_line = '''            if data.get('status') != '1':
                logger.error(f"[EVM Tracker] API error for {wallet_obj.address[:10]}: {data.get('message', 'Unknown')} - Result: {data.get('result', 'None')}")
                return 0'''
    
    content = content.replace(target_line, new_line)
    
    # Also add logging for missing API key
    api_key_line = 'self.api_key = os.environ.get(f"{blockchain.upper()}_API_KEY", "")'
    if api_key_line in content:
        new_api_key_line = '''        self.api_key = os.environ.get(f"{blockchain.upper()}_API_KEY", "")
        if not self.api_key:
            logger.warning(f"[EVM Tracker] No API key for {blockchain}. API calls will fail.")'''
        content = content.replace(api_key_line, new_api_key_line)
    
    # Write back
    with open(file_path, 'w') as f:
        f.write(content)
    
    print(f"✅ Patched {file_path}")
    print("Changes made:")
    print("1. Added error logging for API failures")
    print("2. Added warning for missing API keys")
    print("\n🔧 Restart Celery after patch:")
    print("   sudo systemctl restart celery")
    
    return True

def check_current_implementation():
    """Check current EVMWhaleTracker implementation"""
    file_path = os.path.join(os.path.dirname(__file__), 'dashboard', 'services.py')
    
    with open(file_path, 'r') as f:
        lines = f.readlines()
    
    in_evm_class = False
    for i, line in enumerate(lines):
        if 'class EVMWhaleTracker:' in line:
            in_evm_class = True
            print(f"\n📄 EVMWhaleTracker implementation (lines {i+1}-{min(i+50, len(lines))}):")
        
        if in_evm_class and i < len(lines) - 1:
            print(f"{i+1:3}: {line.rstrip()}")
            if i > 50:  # Show first 50 lines of class
                break

if __name__ == '__main__':
    print("🔧 Patching EVMWhaleTracker for better error logging")
    print("="*60)
    
    check_current_implementation()
    
    response = input("\nApply patch? (y/n): ").lower()
    if response == 'y':
        if patch_evm_tracker():
            print("\n✅ Patch applied successfully")
            print("\n🚀 Next steps:")
            print("1. Restart Celery: sudo systemctl restart celery")
            print("2. Trigger a sync: python manage.py shell")
            print("   >>> from dashboard.tasks import sync_all_whales_task")
            print("   >>> sync_all_whales_task.delay()")
            print("3. Check logs: sudo journalctl -u celery -f")
            print("4. Look for '[EVM Tracker] API error' messages")
        else:
            print("❌ Patch failed")
    else:
        print("⚠️ Patch not applied")