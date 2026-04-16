#!/usr/bin/env python3
"""
Fix Etherscan V2 API migration AND indentation errors in services.py
Run this on VPS to apply all necessary fixes
"""

import os
import re
import shutil
from datetime import datetime

def backup_file(file_path):
    """Create backup of file"""
    backup_path = file_path + '.backup'
    if os.path.exists(file_path):
        shutil.copy2(file_path, backup_path)
        print(f"[OK] Created backup: {backup_path}")
        return backup_path
    return None

def fix_evm_tracker_class(content):
    """Replace EVMWhaleTracker class with V2-compliant version"""
    
    # New EVMWhaleTracker class definition
    new_class = '''class EVMWhaleTracker:
    """Rastreador para redes EVM (Ethereum, Base, etc) usando APIs compatibles con Etherscan V2."""
    API_CONFIG = {
        'ethereum': 'https://api.etherscan.io/api/v2',
        'base': 'https://api.basescan.org/api/v2',
    }

    def __init__(self, blockchain):
        self.blockchain = blockchain
        self.api_url = self.API_CONFIG.get(blockchain, self.API_CONFIG['ethereum'])
        # Cargar keys de .env usando python-decouple
        from decouple import config
        self.api_key = config(f"{blockchain.upper()}_API_KEY", default="")
        if not self.api_key:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"[EVM Tracker] No API key for {blockchain}. API calls will fail.")

    def sync_wallet(self, wallet_obj, max_new=10, **kwargs):
        """Sincroniza transferencias de tokens ERC20 usando Etherscan V2 API."""
        # Etherscan V2 API parameters
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
        
        # V2 API requires User-Agent header
        headers = {
            'User-Agent': 'WhaleTracker/1.0',
            'Accept': 'application/json'
        }
        
        try:
            resp = requests.get(self.api_url, params=params, headers=headers, timeout=12)
            if resp.status_code != 200:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"[EVM Tracker V2] HTTP {resp.status_code} for {wallet_obj.address[:10]}")
                return 0
            
            data = resp.json()
            if data.get('status') != '1':
                error_msg = data.get('message', 'Unknown V2 API error')
                result_msg = data.get('result', 'No result')
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"[EVM Tracker V2] API error for {wallet_obj.address[:10]}: {error_msg} - Result: {result_msg}")
                
                # Special handling for common V2 errors
                if 'rate limit' in error_msg.lower():
                    logger.warning(f"[EVM Tracker V2] Rate limit hit for {self.blockchain}")
                elif 'invalid api key' in error_msg.lower():
                    logger.error(f"[EVM Tracker V2] Invalid API key for {self.blockchain}")
                
                return 0
            
            transfers = data.get('result', [])
            new_txs = 0
            
            for tx in transfers:
                if new_txs >= max_new:
                    break
                
                # Usamos blockNumber + hash para unicidad si hay múltiples transferencias en un hash
                unique_hash = f"{tx['hash']}_{tx.get('logIndex', '0')}"
                if WhaleTransaction.objects.filter(tx_hash=unique_hash).exists():
                    continue
                
                # Parsear timestamp de EVM (está en format string o int según API)
                ts_val = int(tx.get('timeStamp', time.time()))
                timestamp = timezone.make_aware(datetime.fromtimestamp(ts_val))
                
                raw_with_context = dict(tx)
                
                # Capturar contexto de mercado (indicadores técnicos)
                try:
                    from dashboard.whale_intelligence import fetch_market_context
                    token_symbol = tx.get('tokenSymbol')
                    if token_symbol:
                        mkt_ctx = fetch_market_context(token_symbol)
                        if mkt_ctx:
                            raw_with_context['market_context'] = mkt_ctx
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f"[EVM] No se pudo capturar contexto de mercado para {tx.get('tokenSymbol')}: {e}")
                
                WhaleTransaction.objects.create(
                    wallet=wallet_obj,
                    tx_hash=unique_hash,
                    timestamp=timestamp,
                    tx_type="SWAP" if tx.get('to').lower() == wallet_obj.address.lower() else "TRANSFER",
                    from_asset=tx.get('tokenSymbol'), # No lo sabemos aún con certeza, pero tokentx nos da el asset que se movió
                    to_asset=tx.get('tokenSymbol'),
                    amount_in=float(tx.get('value', 0)) / (10 ** int(tx.get('tokenDecimal', 18))),
                    raw_data=raw_with_context
                )
                new_txs += 1
            return new_txs
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"[EVM Tracker] Error sincronizando wallet {wallet_obj.address[:10]}: {e}")
            return 0'''
    
    # Find the EVMWhaleTracker class and replace it
    pattern = r'class EVMWhaleTracker:.*?(?=class \w+:|$)'
    
    # Use DOTALL flag to match across lines
    import re
    new_content = re.sub(pattern, new_class, content, flags=re.DOTALL)
    
    if new_content != content:
        print("[OK] Replaced EVMWhaleTracker class with V2-compliant version")
        return new_content
    else:
        print("[WARNING] Could not find EVMWhaleTracker class to replace")
        return content

def fix_imports(content):
    """Ensure required imports are present"""
    # Check if datetime is imported
    if 'from datetime import datetime' not in content:
        # Add after other imports
        import_line = 'import requests\nimport os\nimport json\nimport time\nimport logging'
        if import_line in content:
            new_import_line = 'import requests\nimport os\nimport json\nimport time\nimport logging\nfrom datetime import datetime'
            content = content.replace(import_line, new_import_line)
            print("[OK] Added datetime import")
    
    return content

def check_indentation(file_path):
    """Check for mixed tabs/spaces indentation"""
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    tab_lines = []
    for i, line in enumerate(lines, 1):
        if '\t' in line:
            tab_lines.append(i)
    
    if tab_lines:
        print(f"[WARNING] Found tabs on lines: {tab_lines[:10]}")
        print("  Converting tabs to spaces...")
        
        # Convert tabs to 4 spaces
        new_lines = []
        for line in lines:
            new_lines.append(line.replace('\t', '    '))
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)
        
        print(f"[OK] Converted tabs to spaces")
        return True
    
    return False

def test_v2_api_quick():
    """Quick test of V2 API"""
    print("\n[TEST] Quick V2 API test...")
    
    test_code = '''
import os
import requests

# Test with environment variable
key = os.environ.get('ETH_API_KEY', '')
if not key:
    print("❌ ETH_API_KEY not in environment")
    exit(1)

print(f"Testing V2 API with key: {key[:12]}...")

# V2 API endpoint
url = "https://api.etherscan.io/api/v2"
params = {
    'module': 'account',
    'action': 'tokentx',
    'address': '0x742d35Cc6634C0532925a3b844Bc9e90F1b6f1d6',
    'startblock': 0,
    'endblock': 99999999,
    'page': 1,
    'offset': 5,
    'sort': 'desc',
    'apikey': key
}
headers = {'User-Agent': 'WhaleTracker/1.0'}

try:
    resp = requests.get(url, params=params, headers=headers, timeout=10)
    print(f"HTTP Status: {resp.status_code}")
    
    import json
    data = resp.json()
    print(f"Status: {data.get('status')}")
    print(f"Message: {data.get('message')}")
    
    if data.get('status') == '1':
        print(f"✅ V2 API WORKING! Found {len(data.get('result', []))} transactions")
    else:
        print(f"❌ V2 API error: {data.get('result', 'Unknown')}")
        
except Exception as e:
    print(f"❌ Connection error: {e}")
'''
    
    test_file = os.path.join(os.path.dirname(__file__), 'quick_v2_test.py')
    with open(test_file, 'w', encoding='utf-8') as f:
        f.write(test_code)
    
    print(f"[+] Created test script: {test_file}")
    return test_file

def main():
    print("[FIX] Fixing V2 API Migration and Indentation Issues")
    print("="*60)
    
    file_path = os.path.join(os.path.dirname(__file__), 'dashboard', 'services.py')
    
    if not os.path.exists(file_path):
        print(f"[ERROR] File not found: {file_path}")
        return
    
    print(f"[+] Target file: {file_path}")
    
    # Create backup
    backup = backup_file(file_path)
    
    # Check indentation
    print("\n[CHECK] Checking indentation...")
    check_indentation(file_path)
    
    # Read current content
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Fix imports
    content = fix_imports(content)
    
    # Fix EVMWhaleTracker class
    print("\n[FIX] Updating EVMWhaleTracker for V2 API...")
    new_content = fix_evm_tracker_class(content)
    
    if new_content == content:
        print("[WARNING] No changes made to EVMWhaleTracker class")
        print("  The class may already be updated or pattern didn't match")
    else:
        # Write updated content
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print("[OK] Updated services.py with V2 API fixes")
    
    # Create test script
    test_file = test_v2_api_quick()
    
    print("\n[OK] Fixes applied successfully!")
    print("\n[NEXT] Next steps:")
    print(f"1. Test V2 API: python {test_file}")
    print("2. Restart Celery: sudo systemctl restart celery")
    print("3. Trigger sync: python manage.py shell")
    print("   >>> from dashboard.tasks import sync_all_whales_task")
    print("   >>> sync_all_whales_task.delay()")
    print("4. Check logs: sudo journalctl -u celery -f")
    print("   Look for 'synced X txs' where X > 0")
    
    print("\n[NOTE] If Celery still crashes with IndentationError:")
    print("   Check line 103 in services.py for mixed tabs/spaces")
    print("   You can manually fix with: sed -i 's/\\t/    /g' dashboard/services.py")
    
    print("\n[TIP] If API still fails:")
    print("   - Wait 5-10 minutes after key creation")
    print("   - Check Etherscan dashboard: https://etherscan.io/myapikey")
    print("   - Consider getting new API keys")

if __name__ == '__main__':
    main()