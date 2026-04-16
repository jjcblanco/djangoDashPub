
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
