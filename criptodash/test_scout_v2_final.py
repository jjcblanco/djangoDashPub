import requests
import json

# API Key del .env del usuario
API_KEY = "NVTVKK7BCHAYQJ71TMAV19BUK62Z5MV1Q4"

def test_pair_proxy_v2_final(token_address, blockchain='base'):
    print(f"--- 📡 Probando Whale Scout v2 para {token_address} ---")
    
    # 1. DexScreener (Usando SEARCH para mayor robustez)
    pair_address = None
    try:
        dex_url = f"https://api.dexscreener.com/latest/dex/search?q={token_address}"
        resp = requests.get(dex_url, timeout=10)
        pairs = resp.json().get('pairs', [])
        if pairs:
            # Filtrar por la cadena correcta si hay varios
            chain_pairs = [p for p in pairs if p.get('chainId') == blockchain]
            if chain_pairs:
                pair_address = chain_pairs[0].get('pairAddress')
                print(f"✅ Par encontrado ({blockchain}): {pair_address}")
    except Exception as e:
        print(f"Error DexScreener: {e}")
        return

    if not pair_address:
        print("❌ No se encontró par en DexScreener.")
        return

    # 2. Basescan tokentx del PAR
    api_url = "https://api.basescan.org/api"
    params = {
        'module': 'account',
        'action': 'tokentx',
        'address': pair_address,
        'sort': 'desc',
        'page': 1,
        'offset': 100,
        'apikey': API_KEY
    }
    
    try:
        resp = requests.get(api_url, params=params, timeout=10)
        data = resp.json()
        if data.get('status') == '1':
            transfers = data.get('result', [])
            print(f"✅ Éxito! {len(transfers)} logs encontrados en el Par.")
            
            buyers = {}
            token_lower = token_address.lower()
            pair_lower = pair_address.lower()
            
            for tx in transfers:
                if tx.get('contractAddress').lower() == token_lower:
                    to_addr = tx.get('to').lower()
                    if to_addr == pair_lower: continue # Si el destino es el par, es venta
                    
                    try:
                        amount = float(tx.get('value')) / (10**int(tx.get('tokenDecimal')))
                        buyers[to_addr] = buyers.get(to_addr, 0) + amount
                    except: pass
            
            sorted_buyers = sorted(buyers.items(), key=lambda x: x[1], reverse=True)
            if sorted_buyers:
                print("🏆 Ballenas encontradas:")
                for addr, vol in sorted_buyers[:5]:
                    print(f"- {addr}: {vol:,.0f} {transfers[0].get('tokenSymbol')}")
            else:
                print("⚠️ No se detectaron compras en los últimos 100 registros del par.")
        else:
            print(f"❌ Error API: {data.get('message')} - {data.get('result')}")
    except Exception as e:
        print(f"Error Final: {e}")

if __name__ == "__main__":
    # DEGEN CORRECTO on Base
    test_pair_proxy_v2_final("0x4ed4e862860bed51a9570b96d89af5e1b0efefed", "base")
