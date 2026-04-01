import requests
import json

def test_geckoterminal(pool_address, network='base'):
    print(f"--- 📡 Probando GeckoTerminal para Pool {pool_address} ---")
    url = f"https://api.geckoterminal.com/api/v2/networks/{network}/pools/{pool_address}/trades"
    
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            trades = data.get('data', [])
            print(f"✅ Éxito! {len(trades)} trades encontrados.")
            
            whales = {}
            for t in trades:
                attr = t.get('attributes', {})
                # Solo compras (buy)
                if attr.get('kind') == 'buy':
                    buyer = attr.get('tx_from_address')
                    # Intentar obtener el volumen en USD
                    vol = float(attr.get('volume_usd') or 0)
                    if buyer:
                        whales[buyer] = whales.get(buyer, 0) + vol
            
            sorted_whales = sorted(whales.items(), key=lambda x: x[1], reverse=True)
            print("🏆 Top Compradores (USD):")
            for addr, vol in sorted_whales[:5]:
                print(f"- {addr}: ${vol:,.2f}")
        else:
            print(f"❌ Error API: {resp.status_code} - {resp.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    # DEGEN Pool on Base
    test_geckoterminal("0xc9034c3E7F58003E6ae0C8438e7c8f4598d5ACAA", "base")
