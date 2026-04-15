#!/usr/bin/env python3
"""
API Key Setup and Verification Tool for Whale Tracking

This script helps verify and configure API keys required for blockchain data
synchronization and notifications.

Supported APIs:
- Etherscan (Ethereum)
- Basescan (Base)
- Solana RPC
- Hyperliquid
- Binance (prices)
- Telegram (notifications)
"""

import os
import sys
import requests
import json
from typing import Dict, List, Optional, Tuple

def setup_django():
    """Configure Django environment"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = script_dir
    
    if not os.path.exists(os.path.join(project_root, 'manage.py')):
        print(f"❌ Error: Could not find manage.py in {project_root}")
        print("Please run this script from the Django project root directory.")
        sys.exit(1)
    
    sys.path.insert(0, project_root)
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')
    
    try:
        import django
        django.setup()
        print(f"✅ Django setup complete")
        return True
    except Exception as e:
        print(f"❌ Django setup failed: {e}")
        return False

def check_etherscan_key(api_key: str) -> Tuple[bool, str]:
    """Test Etherscan API key"""
    if not api_key:
        return False, "No API key provided"
    
    test_address = "0x742d35Cc6634C0532925a3b844Bc9e90F1b6f1d6"  # Vitalik's address
    url = f"https://api.etherscan.io/api?module=account&action=balance&address={test_address}&tag=latest&apikey={api_key}"
    
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        
        if data.get('status') == '1':
            return True, "✅ Valid (balance query successful)"
        elif data.get('message') == 'NOTOK' and 'rate limit' in data.get('result', '').lower():
            return True, "⚠️ Valid but rate limited (normal for free tier)"
        elif data.get('message') == 'NOTOK':
            return False, f"❌ Invalid: {data.get('result', 'Unknown error')}"
        else:
            return False, f"❌ Unexpected response: {data}"
            
    except Exception as e:
        return False, f"❌ Connection error: {e}"

def check_basescan_key(api_key: str) -> Tuple[bool, str]:
    """Test Basescan API key"""
    if not api_key:
        return False, "No API key provided"
    
    test_address = "0x4200000000000000000000000000000000000006"  # WETH on Base
    url = f"https://api.basescan.org/api?module=account&action=balance&address={test_address}&tag=latest&apikey={api_key}"
    
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        
        if data.get('status') == '1':
            return True, "✅ Valid (balance query successful)"
        elif data.get('message') == 'NOTOK' and 'rate limit' in data.get('result', '').lower():
            return True, "⚠️ Valid but rate limited"
        elif data.get('message') == 'NOTOK':
            return False, f"❌ Invalid: {data.get('result', 'Unknown error')}"
        else:
            return False, f"❌ Unexpected response: {data}"
            
    except Exception as e:
        return False, f"❌ Connection error: {e}"

def check_solana_rpc() -> Tuple[bool, str]:
    """Test Solana RPC connectivity"""
    url = "https://api.mainnet-beta.solana.com"
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getHealth"
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        data = response.json()
        
        if 'result' in data:
            return True, "✅ Solana RPC accessible"
        else:
            return False, f"❌ Solana RPC error: {data.get('error', 'Unknown')}"
            
    except Exception as e:
        return False, f"❌ Connection error: {e}"

def check_hyperliquid() -> Tuple[bool, str]:
    """Test Hyperliquid API connectivity"""
    url = "https://api.hyperliquid.xyz/info"
    payload = {"type": "meta"}
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            return True, "✅ Hyperliquid API accessible"
        else:
            return False, f"❌ HTTP {response.status_code}: {response.text[:100]}"
    except Exception as e:
        return False, f"❌ Connection error: {e}"

def check_binance_keys(api_key: str, secret_key: str) -> Tuple[bool, str]:
    """Test Binance API keys"""
    if not api_key or not secret_key:
        return False, "Missing API key or secret"
    
    # Simple test - check server time (no signing required)
    url = "https://api.binance.com/api/v3/time"
    
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return True, "✅ Binance API accessible"
        else:
            return False, f"❌ HTTP {response.status_code}"
    except Exception as e:
        return False, f"❌ Connection error: {e}"

def check_telegram_bot(token: str, chat_id: str) -> Tuple[bool, str]:
    """Test Telegram bot token and chat ID"""
    if not token:
        return False, "No bot token provided"
    
    # Test bot token by getting bot info
    url = f"https://api.telegram.org/bot{token}/getMe"
    
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        
        if data.get('ok'):
            bot_name = data['result']['username']
            
            # Test sending a test message if chat_id provided
            if chat_id:
                msg_url = f"https://api.telegram.org/bot{token}/sendMessage"
                msg_payload = {
                    'chat_id': chat_id,
                    'text': '🔍 Whale Tracking Test: API verification successful!',
                    'parse_mode': 'HTML'
                }
                
                msg_response = requests.post(msg_url, json=msg_payload, timeout=10)
                if msg_response.json().get('ok'):
                    return True, f"✅ Bot @{bot_name} active, message sent to chat {chat_id}"
                else:
                    return True, f"⚠️ Bot @{bot_name} active but cannot send to chat {chat_id}"
            else:
                return True, f"✅ Bot @{bot_name} active (no chat_id to test)"
        else:
            return False, f"❌ Invalid bot token: {data.get('description', 'Unknown error')}"
            
    except Exception as e:
        return False, f"❌ Connection error: {e}"

def check_environment_variables() -> Dict[str, Optional[str]]:
    """Check which API keys are set in environment"""
    keys = {
        'ETH_API_KEY': 'Etherscan (Ethereum)',
        'BASE_API_KEY': 'Basescan (Base)',
        'BINANCE_APIKEY': 'Binance API Key',
        'BINANCE_SECRET': 'Binance Secret',
        'TELEGRAM_BOT_TOKEN': 'Telegram Bot Token',
        'TELEGRAM_CHAT_ID': 'Telegram Chat ID',
    }
    
    results = {}
    for env_key, description in keys.items():
        value = os.environ.get(env_key)
        results[env_key] = {
            'description': description,
            'value': value,
            'set': bool(value),
            'masked': value[:8] + '...' if value and len(value) > 8 else ('***' if value else None)
        }
    
    return results

def interactive_setup():
    """Interactive mode to help set up missing API keys"""
    print("\n" + "="*60)
    print("INTERACTIVE API KEY SETUP")
    print("="*60)
    
    env_vars = check_environment_variables()
    
    for env_key, info in env_vars.items():
        if not info['set']:
            print(f"\n🔑 {info['description']} ({env_key}) is NOT SET")
            response = input(f"Would you like to set it now? (y/n): ").lower()
            
            if response == 'y':
                value = input(f"Enter value for {env_key}: ").strip()
                if value:
                    # Set in current environment
                    os.environ[env_key] = value
                    print(f"✅ {env_key} set in current session")
                    
                    # Ask about making it permanent
                    permanent = input(f"Make this permanent? (Add to .env/apache/systemd) (y/n): ").lower()
                    if permanent == 'y':
                        print("\nTo make permanent, add to one of these:")
                        print(f"1. .env file: {env_key}={value}")
                        print(f"2. Apache config: SetEnv {env_key} \"{value}\"")
                        print(f"3. Systemd service: Environment=\"{env_key}={value}\"")
                        print(f"4. Shell profile: export {env_key}=\"{value}\"")
                else:
                    print(f"⚠️ Skipping {env_key}")
    
    print("\n✅ Interactive setup complete")
    print("Remember to restart services after setting environment variables!")

def generate_config_files():
    """Generate configuration file templates"""
    print("\n" + "="*60)
    print("CONFIGURATION FILE TEMPLATES")
    print("="*60)
    
    # .env template
    env_template = """# Whale Tracking API Keys
# Copy this file to .env in project root and fill in your keys

# Ethereum (Etherscan) - https://etherscan.io/myapikey
ETH_API_KEY=your_etherscan_api_key_here

# Base (Basescan) - https://basescan.org/myapikey
BASE_API_KEY=your_basescan_api_key_here

# Binance - https://www.binance.com/en/my/settings/api-management
BINANCE_APIKEY=your_binance_api_key_here
BINANCE_SECRET=your_binance_secret_here

# Telegram Bot - Create with @BotFather
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
TELEGRAM_CHAT_ID=your_telegram_chat_id_here

# Optional: Solana custom RPC (if you have private RPC)
# SOLANA_RPC_URL=https://your-custom-rpc.com

# Optional: Redis URL for Celery (if not local)
# REDIS_URL=redis://localhost:6379/0
"""
    
    env_path = "api_keys.env.template"
    with open(env_path, 'w') as f:
        f.write(env_template)
    print(f"✅ Created .env template: {env_path}")
    
    # Apache config snippet
    apache_template = """# Apache Environment Variables for Whale Tracking
# Add to your VirtualHost configuration or .htaccess

SetEnv ETH_API_KEY "your_etherscan_api_key_here"
SetEnv BASE_API_KEY "your_basescan_api_key_here"
SetEnv BINANCE_APIKEY "your_binance_api_key_here"
SetEnv BINANCE_SECRET "your_binance_secret_here"
SetEnv TELEGRAM_BOT_TOKEN "your_telegram_bot_token_here"
SetEnv TELEGRAM_CHAT_ID "your_telegram_chat_id_here"
"""
    
    apache_path = "apache_env.conf.template"
    with open(apache_path, 'w') as f:
        f.write(apache_template)
    print(f"✅ Created Apache config template: {apache_path}")
    
    # systemd service snippet
    systemd_template = """# Systemd Environment Variables for Celery/Daphne
# Add to [Service] section of celery.service and daphne.service

Environment="ETH_API_KEY=your_etherscan_api_key_here"
Environment="BASE_API_KEY=your_basescan_api_key_here"
Environment="BINANCE_APIKEY=your_binance_api_key_here"
Environment="BINANCE_SECRET=your_binance_secret_here"
Environment="TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here"
Environment="TELEGRAM_CHAT_ID=your_telegram_chat_id_here"
"""
    
    systemd_path = "systemd_env.conf.template"
    with open(systemd_path, 'w') as f:
        f.write(systemd_template)
    print(f"✅ Created systemd config template: {systemd_path}")

def run_comprehensive_check():
    """Run comprehensive API key verification"""
    print("\n" + "="*60)
    print("COMPREHENSIVE API KEY VERIFICATION")
    print("="*60)
    
    # Check environment variables
    env_vars = check_environment_variables()
    
    print("\n📋 ENVIRONMENT VARIABLE STATUS:")
    for env_key, info in env_vars.items():
        status = "✅ SET" if info['set'] else "❌ MISSING"
        masked = info['masked'] or "(empty)"
        print(f"  {status} {info['description']}: {masked}")
    
    # Test each API
    print("\n🔌 API CONNECTIVITY TESTS:")
    
    # Etherscan
    eth_key = os.environ.get('ETH_API_KEY')
    if eth_key:
        valid, message = check_etherscan_key(eth_key)
        print(f"  Etherscan: {message}")
    else:
        print(f"  Etherscan: ⚠️ No API key set")
    
    # Basescan
    base_key = os.environ.get('BASE_API_KEY')
    if base_key:
        valid, message = check_basescan_key(base_key)
        print(f"  Basescan: {message}")
    else:
        print(f"  Basescan: ⚠️ No API key set")
    
    # Solana (no key needed for public RPC)
    valid, message = check_solana_rpc()
    print(f"  Solana RPC: {message}")
    
    # Hyperliquid (no key needed)
    valid, message = check_hyperliquid()
    print(f"  Hyperliquid: {message}")
    
    # Binance
    binance_key = os.environ.get('BINANCE_APIKEY')
    binance_secret = os.environ.get('BINANCE_SECRET')
    if binance_key and binance_secret:
        valid, message = check_binance_keys(binance_key, binance_secret)
        print(f"  Binance: {message}")
    else:
        print(f"  Binance: ⚠️ Missing API key or secret")
    
    # Telegram
    telegram_token = os.environ.get('TELEGRAM_BOT_TOKEN')
    telegram_chat = os.environ.get('TELEGRAM_CHAT_ID')
    if telegram_token:
        valid, message = check_telegram_bot(telegram_token, telegram_chat)
        print(f"  Telegram: {message}")
    else:
        print(f"  Telegram: ⚠️ No bot token set")
    
    print("\n" + "="*60)
    print("RECOMMENDATIONS:")
    
    recommendations = []
    if not eth_key:
        recommendations.append("1. Get Etherscan API key from https://etherscan.io/myapikey")
    if not base_key:
        recommendations.append("2. Get Basescan API key from https://basescan.org/myapikey")
    if not (binance_key and binance_secret):
        recommendations.append("3. Get Binance API keys from https://www.binance.com/en/my/settings/api-management")
    if not telegram_token:
        recommendations.append("4. Create Telegram bot with @BotFather and get token")
    
    if recommendations:
        for rec in recommendations:
            print(f"  {rec}")
    else:
        print("  ✅ All essential API keys are configured!")
    
    print("\n💡 TIPS:")
    print("  • Free API tiers have rate limits - consider upgrading for many wallets")
    print("  • Store keys in environment variables, NOT in code")
    print("  • Restart Celery and Apache after setting new environment variables")
    print("  • Monitor rate limits in dashboard logs")

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='API Key Setup and Verification Tool')
    parser.add_argument('--check', action='store_true', help='Check current API configurations')
    parser.add_argument('--interactive', action='store_true', help='Interactive setup for missing keys')
    parser.add_argument('--templates', action='store_true', help='Generate configuration templates')
    parser.add_argument('--test', action='store_true', help='Test API connectivity')
    parser.add_argument('--all', action='store_true', help='Run comprehensive check and generate templates')
    
    args = parser.parse_args()
    
    # Setup Django if needed
    if args.check or args.test or args.all:
        if not setup_django():
            return
    
    if args.all:
        run_comprehensive_check()
        generate_config_files()
        return
    
    if args.check:
        run_comprehensive_check()
    
    if args.interactive:
        interactive_setup()
    
    if args.templates:
        generate_config_files()
    
    if args.test:
        run_comprehensive_check()
    
    # Default: show help
    if not any([args.check, args.interactive, args.templates, args.test, args.all]):
        parser.print_help()
        print("\n📝 Examples:")
        print("  python api_key_setup.py --check      # Check current configurations")
        print("  python api_key_setup.py --interactive # Interactive setup")
        print("  python api_key_setup.py --all         # Full verification + templates")

if __name__ == '__main__':
    main()