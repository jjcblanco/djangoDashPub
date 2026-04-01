import requests
import json
import time

def test_logs_refined(contract_address, blockchain='ethereum', api_key=""):
    api_urls = {
        'ethereum': 'https://api.etherscan.io/api',
        'base': 'https://api.basescan.org/api',
    }
    api_url = api_urls.get(blockchain, api_urls['ethereum'])
    
    # 1. Obtener bloque actual
    try:
        resp = requests.get(api_url, params={'module': 'proxy', 'action': 'eth_blockNumber', 'apikey': api_key})
        latest_hex = resp.json().get('result')
        latest_block = int(latest_hex, 16)
        from_block = latest_block - 1000 # Últimas ~3 horas
        print(f"Latest Block: {latest_block}, Scanning from: {from_block}")
    except:
        from_block = "latest"

    # 2. getLogs
    TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
    params = {
        'module': 'logs',
        'action': 'getLogs',
        'fromBlock': str(from_block),
        'toBlock': 'latest',
        'address': contract_address,
        'topic0': TRANSFER_TOPIC,
        'apikey': api_key
    }
    
    try:
        resp = requests.get(api_url, params=params, timeout=10)
        data = resp.json()
        if data.get('status') == '1':
            logs = data.get('result', [])
            print(f"✅ Éxito! Encontrados {len(logs)} logs.")
            if logs:
                last = logs[-1]
                to_addr = "0x" + last['topics'][2][-40:]
                val = int(last['data'], 16)
                print(f"Última compra: {to_addr} -> {val}")
        else:
            print(f"❌ Fallo: {data.get('message')} - {data.get('result')}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    # PEPE
    test_logs_refined("0x6982508145454Ce325dDbE47a25d4ec3d2311933")
