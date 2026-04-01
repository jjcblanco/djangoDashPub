import requests
import json

def debug_dex_search(token_address):
    # Usar el endpoint de búsqueda que es más flexible
    url = f"https://api.dexscreener.com/latest/dex/search?q={token_address}"
    print(f"URL: {url}")
    resp = requests.get(url, timeout=10)
    data = resp.json()
    pairs = data.get('pairs', [])
    
    if pairs:
        print(f"✅ Encontrados {len(pairs)} pares.")
        for p in pairs[:2]:
            print(f"- {p.get('chainId')} | {p.get('dexId')} | {p.get('pairAddress')}")
    else:
        print(f"❌ No se encontraron pares para {token_address}")
        print(f"Response Raw: {data}")

if __name__ == "__main__":
    # DEGEN on Base
    debug_dex_search("0x4edbc9ba274a0399f65133c62553a003c825df24")
