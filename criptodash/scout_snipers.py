import requests
import json
import time
import sys
from datetime import datetime

def scout_snipers(mint_address, rpc_url="https://api.mainnet-beta.solana.com"):
    print(f"\n[SNIPER SCOUT] Analizando token: {mint_address}")
    print("--------------------------------------------------")
    
    # 1. Obtener firmas (buscamos las más antiguas primero)
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getSignaturesForAddress",
        "params": [
            mint_address,
            {"limit": 100} 
        ]
    }
    
    try:
        response = requests.post(rpc_url, json=payload, timeout=15)
        signatures = response.json().get('result', [])
        if not signatures:
            print("No se encontraron transacciones para esta dirección.")
            return
            
        # Ordenar por tiempo ascendente (las más viejas primero)
        signatures.sort(key=lambda x: x['blockTime'] if x.get('blockTime') else 0)
        
        print(f"Se encontraron {len(signatures)} firmas iniciales.")
        print("Buscando los primeros 5 compradores (Early Buyers)...")
        print("")

        found_snipers = []
        processed_txs = 0
        
        for sig in signatures:
            if processed_txs >= 20 or len(found_snipers) >= 5:
                break
                
            tx_hash = sig['signature']
            
            # Obtener detalles de la transacción
            tx_payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getTransaction",
                "params": [
                    tx_hash,
                    {"encoding": "json", "maxSupportedTransactionVersion": 0}
                ]
            }
            
            try:
                tx_resp = requests.post(rpc_url, json=tx_payload, timeout=10)
                tx_data = tx_resp.json().get('result', {})
            except:
                continue
            
            if not tx_data:
                continue
                
            processed_txs += 1
            
            # Intentar identificar quién recibió tokens (postTokenBalances)
            meta = tx_data.get('meta', {})
            if not meta: continue
            
            post_balances = meta.get('postTokenBalances', [])
            for balance in post_balances:
                if balance.get('mint') == mint_address:
                    owner = balance.get('owner')
                    amount = balance.get('uiTokenAmount', {}).get('uiAmount', 0)
                    
                    # Evitar duplicados
                    if owner and owner not in found_snipers and amount > 0:
                        # Ignorar direcciones conocidas de sistema
                        if len(owner) > 30 and owner != mint_address:
                            found_snipers.append(owner)
                            time_str = datetime.fromtimestamp(sig['blockTime']).strftime('%H:%M:%S')
                            print(f"Sniper #{len(found_snipers)} detectado!")
                            print(f"   Address: {owner}")
                            print(f"   Time: {time_str}")
                            print(f"   Amount: {amount}")
                            print("-" * 20)
            
        if not found_snipers:
            print("No se pudieron identificar compradores claros en las primeras transacciones.")
        else:
            print(f"\nBusqueda completada! Se identificaron {len(found_snipers)} posibles insiders/snipers.")
            print("\nCopia estas direcciones en tu Dashboard para seguirlas:")
            for addr in found_snipers:
                print(f"   {addr}")
                
    except Exception as e:
        print(f"Error durante el escaneo: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python scout_snipers.py <MINT_ADDRESS_DEL_TOKEN>")
        sys.exit(1)
        
    token_address = sys.argv[1]
    scout_snipers(token_address)
