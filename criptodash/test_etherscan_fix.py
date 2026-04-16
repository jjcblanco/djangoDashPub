"""
Test rápido de Etherscan V2 API para Ethereum y Base.
Ejecutar: python test_etherscan_fix.py
"""
import os
import sys
import requests

# Cargar .env manualmente
env_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, val = line.split('=', 1)
                os.environ.setdefault(key.strip(), val.strip())

API_KEY = os.environ.get('ETH_API_KEY', '')
API_URL = 'https://api.etherscan.io/v2/api'

# Etherscan V2 unificada: mismo endpoint, diferente chainid
TEST_WALLETS = {
    'ethereum': {
        'chainid': 1,
        'address': '0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045',  # vitalik.eth
        'label': 'vitalik.eth (ETH)',
    },
    'base': {
        'chainid': 8453,
        'address': '0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045',  # vitalik.eth en Base
        'label': 'vitalik.eth (Base)',
    },
}

def test_chain(chain_name, config):
    api_url = config['api_url']
    chainid = config.get('chainid')
    print(f"\n{'='*50}")
    print(f"[TEST] {chain_name.upper()} ({'V2 chainid=' + str(chainid) if chainid else 'endpoint directo'})")
    print(f"   URL: {api_url}")
    print(f"   Wallet: {config['label']}")
    print(f"   Address: {config['address'][:12]}...")
    print(f"   API Key: {API_KEY[:12]}...")
    
    params = {
        'module': 'account',
        'action': 'tokentx',
        'address': config['address'],
        'startblock': 0,
        'endblock': 99999999,
        'page': 1,
        'offset': 5,
        'sort': 'desc',
        'apikey': API_KEY,
    }
    if chainid is not None:
        params['chainid'] = chainid
    headers = {
        'User-Agent': 'WhaleTracker/1.0',
        'Accept': 'application/json',
    }
    
    try:
        resp = requests.get(api_url, params=params, headers=headers, timeout=12)
        print(f"\n   HTTP Status: {resp.status_code}")
        
        if resp.status_code != 200:
            print(f"   ❌ Error HTTP: {resp.status_code}")
            print(f"   Response: {resp.text[:200]}")
            return False
        
        data = resp.json()
        status = data.get('status')
        message = data.get('message', '')
        result = data.get('result', [])
        
        print(f"   API Status: {status}")
        print(f"   API Message: {message}")
        
        if status == '1' and isinstance(result, list):
            print(f"   ✅ ¡FUNCIONA! {len(result)} transacciones encontradas")
            if result:
                tx = result[0]
                print(f"\n   📝 Última transacción:")
                print(f"      Hash: {tx.get('hash', 'N/A')[:16]}...")
                print(f"      Token: {tx.get('tokenName', 'N/A')} ({tx.get('tokenSymbol', '?')})")
                print(f"      From: {tx.get('from', 'N/A')[:12]}...")
                print(f"      To: {tx.get('to', 'N/A')[:12]}...")
                
                # Calcular monto real
                value = float(tx.get('value', 0))
                decimals = int(tx.get('tokenDecimal', 18))
                real_amount = value / (10 ** decimals)
                print(f"      Amount: {real_amount:,.4f} {tx.get('tokenSymbol', '?')}")
            return True
        else:
            print(f"   ❌ Error de API: {message}")
            if isinstance(result, str):
                print(f"   Detalle: {result}")
            
            if 'invalid api' in str(message).lower() or 'invalid api' in str(result).lower():
                print(f"\n   💡 Tu API key parece inválida. Verifica en: https://etherscan.io/myapikey")
            elif 'rate limit' in str(message).lower():
                print(f"\n   💡 Rate limit alcanzado. Espera unos segundos e intenta de nuevo.")
            elif 'No transactions found' in str(message):
                print(f"\n   ℹ️  No hay transacciones ERC20 para esta wallet (puede ser normal)")
                return True  # No es un error de API
            return False
            
    except requests.exceptions.Timeout:
        print(f"   ❌ Timeout - el servidor no respondió en 12s")
        return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

def main():
    print("🐋 Test de Etherscan V2 API — Fix Verification")
    print(f"   Ethereum: Etherscan V2 API")
    print(f"   Base: Basescan API directa")
    
    if not API_KEY:
        print("\n❌ ETH_API_KEY no encontrada en el .env")
        print("   Asegúrate de que existe en criptodash/.env")
        sys.exit(1)
    
    print(f"   API Key: {API_KEY[:12]}... ({'OK' if len(API_KEY) > 10 else 'MUY CORTA'})")
    
    results = {}
    for chain_name, config in TEST_WALLETS.items():
        results[chain_name] = test_chain(chain_name, config)
        # Pequeño delay entre chains para evitar rate limit
        import time
        time.sleep(0.5)
    
    # Resumen
    print(f"\n{'='*50}")
    print("📊 RESUMEN:")
    for chain, ok in results.items():
        status = "✅ OK" if ok else "❌ FALLO"
        print(f"   {chain.upper():12s} → {status}")
    
    all_ok = all(results.values())
    if all_ok:
        print(f"\n🎉 ¡Todas las redes funcionan! Ya puedes desplegar al VPS.")
    else:
        print(f"\n⚠️  Hay redes con problemas. Revisa los errores arriba.")
    
    return 0 if all_ok else 1

if __name__ == '__main__':
    sys.exit(main())
