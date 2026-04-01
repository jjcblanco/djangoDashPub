import requests
import json

def debug_dex(token_address):
    url = f"https://api.dexscreener.com/latest/dex/tokens/{token_address}"
    print(f"URL: {url}")
    resp = requests.get(url, timeout=10)
    print(f"Status: {resp.status_code}")
    data = resp.json()
    pairs = data.get('pairs', [])
    print(f"Pairs found: {len(pairs)}")
    if pairs:
        for p in pairs[:2]:
            print(f"- {p.get('dexId')} | {p.get('pairAddress')} | Liquidity: {p.get('liquidity', {}).get('usd')}")
    else:
        print(f"Response: {data}")

if __name__ == "__main__":
    # DEGEN on Base
    debug_dex("0x4edbc9ba274a0399f65133c62553a003c825df24")
