#!/usr/bin/env python3
"""
Detailed API key diagnostic
Tests each blockchain API and shows exact errors
"""

import os
import sys
import requests
import json
from pathlib import Path

def load_from_env_file():
    """Try to load keys from .env file using python-decouple"""
    try:
        from decouple import Config, RepositoryEnv
        env_path = Path(__file__).resolve().parent / '.env'
        if env_path.exists():
            config = Config(RepositoryEnv(str(env_path)))
            return config
        return None
    except ImportError:
        print("⚠️ python-decouple not installed")
        return None
    except Exception as e:
        print(f"⚠️ Error loading .env: {e}")
        return None

def test_key_source(key_name):
    """Check where a key is coming from"""
    env_value = os.environ.get(key_name)
    
    config = load_from_env_file()
    dotenv_value = None
    if config:
        try:
            dotenv_value = config(key_name)
        except:
            dotenv_value = None
    
    print(f"\n🔍 {key_name}:")
    if env_value:
        print(f"  ✅ In ENVIRONMENT: {env_value[:12]}...")
    else:
        print(f"  ❌ NOT in environment variables")
    
    if dotenv_value:
        print(f"  ✅ In .env FILE: {dotenv_value[:12]}...")
    else:
        print(f"  ❌ NOT in .env file")
    
    return env_value or dotenv_value

def test_etherscan_api(key):
    """Test Etherscan API with detailed error reporting"""
    print(f"\n🔌 Testing Etherscan API with key: {key[:12]}...")
    
    # Test 1: Simple balance check (least expensive)
    url = "https://api.etherscan.io/api"
    params = {
        'module': 'account',
        'action': 'balance',
        'address': '0x742d35Cc6634C0532925a3b844Bc9e90F1b6f1d6',  # Vitalik
        'tag': 'latest',
        'apikey': key
    }
    
    try:
        resp = requests.get(url, params=params, timeout=10)
        print(f"  HTTP Status: {resp.status_code}")
        
        data = resp.json()
        print(f"  Response: {json.dumps(data, indent=2)}")
        
        if data.get('status') == '1':
            print(f"  ✅ Etherscan API WORKING")
            balance = int(data.get('result', 0)) / 10**18
            print(f"  Balance: {balance:.4f} ETH")
            return True
        else:
            error_msg = data.get('result', data.get('message', 'Unknown'))
            print(f"  ❌ Etherscan ERROR: {error_msg}")
            
            # Check for common errors
            if 'rate limit' in error_msg.lower():
                print(f"  ⚠️ RATE LIMITED - Free tier (5 calls/sec, 100k/day)")
                print(f"  💡 Get new key: https://etherscan.io/myapikey")
            elif 'invalid api key' in error_msg.lower():
                print(f"  ⚠️ INVALID API KEY")
                print(f"  💡 Get new key: https://etherscan.io/myapikey")
            elif 'missing api key' in error_msg.lower():
                print(f"  ⚠️ API KEY MISSING in request")
                print(f"  💡 Check if key is being passed correctly")
            return False
            
    except Exception as e:
        print(f"  ❌ Connection error: {e}")
        return False

def test_basescan_api(key):
    """Test Basescan API with detailed error reporting"""
    print(f"\n🔌 Testing Basescan API with key: {key[:12]}...")
    
    url = "https://api.basescan.org/api"
    params = {
        'module': 'account',
        'action': 'balance',
        'address': '0x4200000000000000000000000000000000000006',  # WETH
        'tag': 'latest',
        'apikey': key
    }
    
    try:
        resp = requests.get(url, params=params, timeout=10)
        print(f"  HTTP Status: {resp.status_code}")
        
        data = resp.json()
        print(f"  Response: {json.dumps(data, indent=2)}")
        
        if data.get('status') == '1':
            print(f"  ✅ Basescan API WORKING")
            return True
        else:
            error_msg = data.get('result', data.get('message', 'Unknown'))
            print(f"  ❌ Basescan ERROR: {error_msg}")
            return False
            
    except Exception as e:
        print(f"  ❌ Connection error: {e}")
        return False

def test_solana_rpc():
    """Test Solana RPC (no key needed)"""
    print(f"\n🔌 Testing Solana RPC...")
    
    url = "https://api.mainnet-beta.solana.com"
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getHealth"
    }
    
    try:
        resp = requests.post(url, json=payload, timeout=10)
        print(f"  HTTP Status: {resp.status_code}")
        
        data = resp.json()
        if 'result' in data:
            print(f"  ✅ Solana RPC WORKING")
            return True
        else:
            print(f"  ❌ Solana ERROR: {data.get('error', 'Unknown')}")
            return False
            
    except Exception as e:
        print(f"  ❌ Connection error: {e}")
        return False

def check_rate_limit_impact():
    """Estimate if we're hitting rate limits"""
    print(f"\n📊 RATE LIMIT ANALYSIS:")
    
    # Etherscan free tier: 5 calls/sec, 100,000 calls/day
    # Basescan free tier: similar
    
    wallets = 73  # From diagnostic
    calls_per_wallet = 1  # Each sync makes 1 API call (tokentx)
    sync_interval_minutes = 15  # Celery Beat schedule
    
    calls_per_hour = wallets * (60 / sync_interval_minutes)
    calls_per_day = calls_per_hour * 24
    
    print(f"  Wallets: {wallets}")
    print(f"  Sync interval: {sync_interval_minutes} minutes")
    print(f"  Estimated calls/hour: {calls_per_hour:.1f}")
    print(f"  Estimated calls/day: {calls_per_day:.1f}")
    
    if calls_per_day > 100000:
        print(f"  ⚠️ EXCEEDS Etherscan free tier (100k/day)")
        print(f"  💡 Solutions:")
        print(f"    1. Increase sync interval (currently {sync_interval_minutes}min)")
        print(f"    2. Get paid API tier")
        print(f"    3. Implement better rate limiting")
    elif calls_per_day > 50000:
        print(f"  ⚠️ Close to Etherscan limit")
    else:
        print(f"  ✅ Within free tier limits")

def main():
    print("🔍 DETAILED API DIAGNOSTIC")
    print("="*60)
    
    # Check .env file
    env_path = Path(__file__).resolve().parent / '.env'
    print(f"\n📁 .env file: {env_path}")
    if env_path.exists():
        print(f"  ✅ EXISTS")
        try:
            with open(env_path, 'r') as f:
                lines = [l.strip() for l in f.readlines() if l.strip() and not l.startswith('#')]
            print(f"  Contains {len(lines)} config lines")
            for line in lines[:5]:  # Show first 5
                print(f"    {line}")
            if len(lines) > 5:
                print(f"    ... and {len(lines)-5} more")
        except Exception as e:
            print(f"  ❌ Error reading: {e}")
    else:
        print(f"  ❌ NOT FOUND")
    
    # Test each key source
    eth_key = test_key_source('ETH_API_KEY')
    base_key = test_key_source('BASE_API_KEY')
    
    # Test APIs
    if eth_key:
        test_etherscan_api(eth_key)
    
    if base_key:
        test_basescan_api(base_key)
    else:
        print(f"\n⚠️ No Basescan key to test")
    
    test_solana_rpc()
    
    check_rate_limit_impact()
    
    print(f"\n" + "="*60)
    print("💡 RECOMMENDATIONS:")
    
    recommendations = []
    
    if not eth_key:
        recommendations.append("1. Get Etherscan API key from https://etherscan.io/myapikey")
    elif 'NVTVKK7B' in (eth_key or ''):
        recommendations.append("2. Your Etherscan key starts with NVTVKK7B - verify it's valid")
    
    if not base_key:
        recommendations.append("3. Get Basescan API key from https://basescan.org/myapikey")
    elif base_key == eth_key:
        recommendations.append("4. Using SAME key for Etherscan & Basescan - may cause rate limiting")
    
    if recommendations:
        for i, rec in enumerate(recommendations, 1):
            print(f"  {rec}")
    else:
        print("  ✅ All API keys should be working")
    
    print(f"\n🔧 QUICK FIXES:")
    print("  1. If keys in .env but not in environment:")
    print("     sudo nano /etc/systemd/system/celery.service")
    print("     Add: Environment=\"ETH_API_KEY=your_key\"")
    print("  2. Restart: sudo systemctl restart celery apache2")
    print("  3. Test: python test_api_detailed.py")

if __name__ == '__main__':
    main()