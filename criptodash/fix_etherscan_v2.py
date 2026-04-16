#!/usr/bin/env python3
"""
Fix Etherscan API V2 Migration Issue
Updates EVMWhaleTracker to use Etherscan V2 API endpoints
"""

import os
import re

def update_evm_tracker():
    """Update EVMWhaleTracker to use Etherscan V2 API"""
    file_path = os.path.join(os.path.dirname(__file__), 'dashboard', 'services.py')
    
    if not os.path.exists(file_path):
        print(f"❌ File not found: {file_path}")
        return False
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    print("🔧 Updating EVMWhaleTracker for Etherscan V2 API...")
    
    # 1. Update API_CONFIG to use V2 endpoints
    old_api_config = """    API_CONFIG = {
        'ethereum': 'https://api.etherscan.io/api',
        'base': 'https://api.basescan.org/api',
    }"""
    
    new_api_config = """    API_CONFIG = {
        'ethereum': 'https://api.etherscan.io/api/v2',
        'base': 'https://api.basescan.org/api/v2',
    }"""
    
    if old_api_config in content:
        content = content.replace(old_api_config, new_api_config)
        print("✅ Updated API endpoints to V2")
    else:
        print("⚠️ API_CONFIG not found or already updated")
    
    # 2. Update the sync_wallet method to use V2 parameters
    # Find the sync_wallet method and update params
    sync_wallet_start = '    def sync_wallet(self, wallet_obj, max_new=10, **kwargs):'
    if sync_wallet_start in content:
        # Look for the params section
        params_pattern = r'params = \{.*?apikey.*?\}'
        
        # New V2 parameters for token transfers
        old_params = """        params = {
            'module': 'account',
            'action': 'tokentx',
            'address': wallet_obj.address,
            'sort': 'desc',
            'page': 1,
            'offset': 50,
            'apikey': self.api_key
        }"""
        
        new_params = """        # Etherscan V2 API parameters
        params = {
            'module': 'account',
            'action': 'tokentx',
            'address': wallet_obj.address,
            'startblock': 0,
            'endblock': 99999999,
            'page': 1,
            'offset': 50,
            'sort': 'desc',
            'apikey': self.api_key
        }
        
        # V2 API requires these additional headers
        headers = {
            'User-Agent': 'WhaleTracker/1.0',
            'Accept': 'application/json'
        }"""
        
        if old_params in content:
            content = content.replace(old_params, new_params)
            print("✅ Updated parameters for V2 API")
        else:
            print("⚠️ Parameters section not found or already updated")
        
        # Update the request to include headers
        old_request = '            resp = requests.get(self.api_url, params=params, timeout=12)'
        new_request = '            resp = requests.get(self.api_url, params=params, headers=headers, timeout=12)'
        
        if old_request in content:
            content = content.replace(old_request, new_request)
            print("✅ Updated request to include headers")
        else:
            print("⚠️ Request line not found or already updated")
    
    # 3. Add better error logging for V2 responses
    error_check_pattern = 'if data.get(\'status\') != \'1\': return 0'
    
    if error_check_pattern in content:
        # Replace with better error handling
        new_error_check = '''            if data.get('status') != '1':
                error_msg = data.get('message', 'Unknown V2 API error')
                result_msg = data.get('result', 'No result')
                logger.error(f"[EVM Tracker V2] API error for {wallet_obj.address[:10]}: {error_msg} - Result: {result_msg}")
                
                # Special handling for common V2 errors
                if 'rate limit' in error_msg.lower():
                    logger.warning(f"[EVM Tracker V2] Rate limit hit for {self.blockchain}")
                elif 'invalid api key' in error_msg.lower():
                    logger.error(f"[EVM Tracker V2] Invalid API key for {self.blockchain}")
                
                return 0'''
        
        content = content.replace(error_check_pattern, new_error_check)
        print("✅ Added V2 API error logging")
    
    # 4. Add import for datetime if not present
    if 'from datetime import datetime' not in content and 'datetime.fromtimestamp' in content:
        # Find the imports section
        import_section = 'import requests\nimport os\nimport json\nimport time\nimport logging'
        if import_section in content:
            new_import_section = 'import requests\nimport os\nimport json\nimport time\nimport logging\nfrom datetime import datetime'
            content = content.replace(import_section, new_import_section)
            print("✅ Added datetime import")
    
    # Write back the updated file
    with open(file_path, 'w') as f:
        f.write(content)
    
    print(f"\n✅ Successfully updated {file_path} for Etherscan V2 API")
    return True

def test_v2_api():
    """Test the V2 API with current configuration"""
    print("\n🧪 Testing V2 API configuration...")
    
    test_code = '''
import os
import requests

def test_etherscan_v2():
    """Test Etherscan V2 API"""
    key = os.environ.get('ETH_API_KEY', 'NVTVKK7BCHAY...')
    
    # V2 API endpoint
    url = "https://api.etherscan.io/api/v2"
    
    # V2 parameters
    params = {
        'module': 'account',
        'action': 'tokentx',
        'address': '0x742d35Cc6634C0532925a3b844Bc9e90F1b6f1d6',
        'startblock': 0,
        'endblock': 99999999,
        'page': 1,
        'offset': 10,
        'sort': 'desc',
        'apikey': key
    }
    
    headers = {
        'User-Agent': 'WhaleTracker/1.0',
        'Accept': 'application/json'
    }
    
    try:
        print(f"Testing V2 API with key: {key[:12]}...")
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        print(f"HTTP Status: {resp.status_code}")
        
        import json
        data = resp.json()
        print(f"Response: {json.dumps(data, indent=2)}")
        
        if data.get('status') == '1':
            print("✅ V2 API WORKING!")
            print(f"Found {len(data.get('result', []))} token transactions")
            return True
        else:
            error_msg = data.get('message', 'Unknown')
            print(f"❌ V2 API error: {error_msg}")
            print(f"Result: {data.get('result', 'None')}")
            return False
            
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False

# Also test Basescan V2
def test_basescan_v2():
    key = os.environ.get('BASE_API_KEY', os.environ.get('ETH_API_KEY', ''))
    if not key:
        print("No Basescan key to test")
        return False
    
    url = "https://api.basescan.org/api/v2"
    params = {
        'module': 'account',
        'action': 'tokentx',
        'address': '0x4200000000000000000000000000000000000006',
        'startblock': 0,
        'endblock': 99999999,
        'page': 1,
        'offset': 10,
        'sort': 'desc',
        'apikey': key
    }
    
    headers = {
        'User-Agent': 'WhaleTracker/1.0',
        'Accept': 'application/json'
    }
    
    try:
        print(f"\\nTesting Basescan V2 API...")
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        print(f"HTTP Status: {resp.status_code}")
        
        import json
        data = resp.json()
        
        if data.get('status') == '1':
            print("✅ Basescan V2 API WORKING!")
            return True
        else:
            print(f"❌ Basescan V2 error: {data.get('message', 'Unknown')}")
            return False
            
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False

# Run tests
test_etherscan_v2()
test_basescan_v2()
'''
    
    # Save test script
    test_file = os.path.join(os.path.dirname(__file__), 'test_v2_api.py')
    with open(test_file, 'w') as f:
        f.write(test_code)
    
    print(f"📄 Created test script: {test_file}")
    print("Run it with: python test_v2_api.py")
    
    return test_file

def main():
    print("🔧 Fixing Etherscan V2 API Migration Issue")
    print("="*60)
    
    print("\n📋 Current Issue:")
    print("  ❌ Using deprecated V1 API endpoints")
    print("  ✅ API keys are valid")
    print("  🔄 Need to update to V2 API")
    
    print("\n🔧 Changes to be made:")
    print("  1. Update API endpoints from /api to /api/v2")
    print("  2. Add V2 API parameters (startblock, endblock)")
    print("  3. Add User-Agent headers")
    print("  4. Improve error logging for V2 responses")
    
    response = input("\nApply V2 API fix? (y/n): ").lower()
    if response == 'y':
        if update_evm_tracker():
            test_file = test_v2_api()
            
            print("\n✅ Fix applied successfully!")
            print("\n🚀 Next steps:")
            print("1. Test V2 API: python test_v2_api.py")
            print("2. Restart Celery: sudo systemctl restart celery")
            print("3. Trigger sync: python manage.py shell")
            print("   >>> from dashboard.tasks import sync_all_whales_task")
            print("   >>> sync_all_whales_task.delay()")
            print("4. Check logs: sudo journalctl -u celery -f")
            print("   Look for 'synced X txs' where X > 0")
            
            print("\n📝 Note: If V2 API still fails, you may need to:")
            print("  - Wait for new keys to propagate (5-10 min)")
            print("  - Check Etherscan dashboard for API usage")
            print("  - Consider paid API tier if hitting limits")
        else:
            print("❌ Fix failed")
    else:
        print("⚠️ Fix not applied")

if __name__ == '__main__':
    main()