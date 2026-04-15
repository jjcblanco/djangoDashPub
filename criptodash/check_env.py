#!/usr/bin/env python3
"""
Quick check of .env file and environment variables on VPS
Run: python check_env.py
"""

import os
import sys
from pathlib import Path

def main():
    print("🔍 Checking .env file and environment variables")
    print("="*60)
    
    # Get project root (same as script location)
    script_dir = Path(__file__).resolve().parent
    env_path = script_dir / '.env'
    
    print(f"Project directory: {script_dir}")
    print(f".env file path: {env_path}")
    
    # Check if .env exists
    if env_path.exists():
        print(f"✅ .env file EXISTS")
        
        # Try to read .env content
        try:
            with open(env_path, 'r') as f:
                lines = f.readlines()
                
            print(f"\n📄 .env content ({len(lines)} lines):")
            for line in lines[:20]:  # Show first 20 lines
                line = line.strip()
                if line and not line.startswith('#'):
                    print(f"  {line}")
            if len(lines) > 20:
                print(f"  ... and {len(lines) - 20} more lines")
                
            # Check for specific keys
            target_keys = ['ETH_API_KEY', 'BASE_API_KEY', 'BINANCE_APIKEY', 
                          'BINANCE_SECRET', 'TELEGRAM_BOT_TOKEN', 'TELEGRAM_CHAT_ID']
            
            print(f"\n🔑 Looking for API keys in .env:")
            for key in target_keys:
                found = False
                for line in lines:
                    if line.strip().startswith(f'{key}='):
                        value = line.strip().split('=', 1)[1]
                        masked = value[:8] + '...' if len(value) > 8 else '***'
                        print(f"  ✅ {key}: FOUND ({masked})")
                        found = True
                        break
                if not found:
                    print(f"  ❌ {key}: NOT FOUND in .env")
                    
        except Exception as e:
            print(f"❌ Error reading .env: {e}")
    else:
        print(f"❌ .env file NOT FOUND")
        
    print(f"\n" + "="*60)
    print("ENVIRONMENT VARIABLES:")
    
    # Check environment variables
    target_keys = ['ETH_API_KEY', 'BASE_API_KEY', 'BINANCE_APIKEY', 
                  'BINANCE_SECRET', 'TELEGRAM_BOT_TOKEN', 'TELEGRAM_CHAT_ID']
    
    for key in target_keys:
        value = os.environ.get(key)
        if value:
            masked = value[:8] + '...' if len(value) > 8 else '***'
            print(f"  ✅ {key}: SET in environment ({masked})")
        else:
            print(f"  ❌ {key}: NOT SET in environment")
    
    print(f"\n" + "="*60)
    print("PYTHON-DECOUPLE TEST:")
    
    # Try to load using python-decouple
    try:
        from decouple import Config, RepositoryEnv
        config = Config(RepositoryEnv(str(env_path)))
        print("✅ python-decouple is installed")
        
        for key in target_keys:
            try:
                value = config(key)
                masked = value[:8] + '...' if len(value) > 8 else '***'
                print(f"  ✅ {key}: Loaded via decouple ({masked})")
            except:
                print(f"  ❌ {key}: NOT loaded via decouple")
                
    except ImportError:
        print("❌ python-decouple NOT installed")
        print("   Install: pip install python-decouple")
    except Exception as e:
        print(f"❌ Error using python-decouple: {e}")
    
    print(f"\n" + "="*60)
    print("RECOMMENDATIONS:")
    
    if env_path.exists():
        print("1. .env file exists but keys may not be loading into environment")
        print("2. For Apache/mod_wsgi, add environment variables to Apache config:")
        print("   SetEnv ETH_API_KEY \"your_key\"")
        print("   SetEnv BASE_API_KEY \"your_key\"")
        print("   ... etc")
        print("3. For Celery systemd service, add to service file:")
        print("   Environment=\"ETH_API_KEY=your_key\"")
        print("   Environment=\"BASE_API_KEY=your_key\"")
        print("   ... etc")
        print("4. OR ensure python-decouple is installed and .env is readable")
    else:
        print("1. Create .env file with API keys")
        print("2. Copy from .env.example if exists")
        
    print(f"\n💡 Quick fix: Source .env before running commands")
    print(f"   source {env_path}  # Then run your diagnostic")

if __name__ == '__main__':
    main()