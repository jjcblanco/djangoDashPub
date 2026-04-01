import requests
import json
import os

# API Key del .env del usuario
API_KEY = "NVTVKK7BCHAYQJ71TMAV19BUK62Z5MV1Q4"

def test_pair_proxy_v2(token_address, blockchain='base'):
    print(f"--- 📡 Probando Whale Scout v2 (Pair-Proxy) para {token_address} ---")
    
    # 1. DexScreener
    pair_address = None
    try:
        dex_url = f"https://api.dexscreener.com/latest/dex/tokens/{token_address}"
        resp = requests.get(dex_url, timeout=10)
        pairs = resp.json().get('pairs', [])
        if pairs:
            pair_address = pairs[0].get('pairAddress')
            print(f"✅ Par encontrado: {pair_address}")
    except Exception as e:
        print(f"Error DexScreener: {e}")
        return

    if not pair_address:
        print("❌ No se encontró par.")
        return

    # 2. Etherscan/Basescan tokentx del PAR
    api_url = "https://api.basescan.org/api"
    params = {
        'module': 'account',
        'action': 'tokentx',
        'address': pair_address,
        'sort': 'desc',
        'page': 1,
        'offset': 50,
        'apikey': API_KEY
    }
    
    try:
        resp = requests.get(api_url, params=params, timeout=10)
        data = resp.json()
        if data.get('status') == '1':
            transfers = data.get('result', [])
            print(f"✅ Éxito! {len(transfers)} logs encontrados.")
            
            buyers = {}
            token_lower = token_address.lower()
            pair_lower = pair_address.lower()
            
            for tx in transfers:
                if tx.get('contractAddress').lower() == token_lower:
                    to_addr = tx.get('to').lower()
                    if to_addr == pair_lower: continue
                    
                    amount = float(tx.get('value')) / (10**int(tx.get('tokenDecimal')))
                    buyers[to_addr] = buyers.get(to_addr, 0) + amount
            
            sorted_buyers = sorted(buyers.items(), key=lambda x: x[1], reverse=True)
            if sorted_buyers:
                print("🏆 Ballenas encontradas:")
                for addr, vol in sorted_buyers[:5]:
                    print(f"- {addr}: {vol:,.0f} tokens")
            else:
                print("⚠️ No se encontraron compras del TOKEN específico en el par recientemente.")
        else:
            print(f"❌ Error API: {data.get('message')} - {data.get('result')}")
    except Exception as e:
        print(f"Error Final: {e}")

if __name__ == "__main__":
    # TOSHI on Base
    test_pair_proxy_v2("0xac1e8d646be220516fc98b1a8f6d773ff4d226f9")
