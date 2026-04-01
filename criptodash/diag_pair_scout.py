import requests
import json

def test_pair_proxy(token_address, blockchain='ethereum', api_key=""):
    print(f"--- 📡 Probando Estrategia 'Pair Proxy' para {token_address} ---")
    
    # 1. Buscar el Par en DexScreener
    try:
        dex_url = f"https://api.dexscreener.com/latest/dex/tokens/{token_address}"
        resp = requests.get(dex_url, timeout=10)
        dex_data = resp.json()
        pairs = dex_data.get('pairs', [])
        if not pairs:
            print("❌ No se encontró un Par de Liquidez en DexScreener.")
            return
        
        # Usar el primer par (el de mayor liquidez usualmente)
        pair_address = pairs[0].get('pairAddress')
        print(f"✅ Par encontrado: {pair_address} ({pairs[0].get('dexId')})")
    except Exception as e:
        print(f"Error buscando par: {e}")
        return

    # 2. Escanear tokentx del PAR (no del token)
    api_urls = {
        'ethereum': 'https://api.etherscan.io/api',
        'base': 'https://api.basescan.org/api',
    }
    api_url = api_urls.get(blockchain, api_urls['ethereum'])
    
    params = {
        'module': 'account',
        'action': 'tokentx',
        'address': pair_address, # Escaneamos al PAR
        'sort': 'desc',
        'page': 1,
        'offset': 100,
        'apikey': api_key
    }
    
    try:
        resp = requests.get(api_url, params=params, timeout=10)
        data = resp.json()
        if data.get('status') == '1':
            transfers = data.get('result', [])
            print(f"✅ Éxito! {len(transfers)} transferencias encontradas en el Par.")
            
            # 3. Filtrar los que recibieron el TOKEN (esto son compras o retiros de LP)
            whales = {}
            for tx in transfers:
                if tx.get('contractAddress').lower() == token_address.lower():
                    to_addr = tx.get('to').lower()
                    if to_addr == pair_address.lower(): continue # Omitir si el destino es el par (ventas)
                    
                    amount = float(tx.get('value')) / (10**int(tx.get('tokenDecimal')))
                    whales[to_addr] = whales.get(to_addr, 0) + amount
            
            sorted_whales = sorted(whales.items(), key=lambda x: x[1], reverse=True)
            print("🏆 Top 5 Compradores en este Par:")
            for addr, vol in sorted_whales[:5]:
                print(f"- {addr}: {vol:,.0f} tokens")
        else:
            print(f"❌ API Error: {data.get('message')} - {data.get('result')}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    # PEPE
    test_pair_proxy("0x6982508145454Ce325dDbE47a25d4ec3d2311933")
