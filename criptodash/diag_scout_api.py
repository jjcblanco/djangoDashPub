import requests
import json

def debug_api(contract_address, blockchain='ethereum', api_key=""):
    api_urls = {
        'ethereum': 'https://api.etherscan.io/api',
        'base': 'https://api.basescan.org/api',
    }
    api_url = api_urls.get(blockchain, api_urls['ethereum'])
    
    # Intento 1: tokentx con contractaddress pero SIN address (billetera)
    params = {
        'module': 'account',
        'action': 'tokentx',
        'contractaddress': contract_address,
        'sort': 'desc',
        'page': 1,
        'offset': 10,
        'apikey': api_key
    }
    
    print(f"--- 📡 Probando tokentx SIN address para {contract_address} ---")
    try:
        resp = requests.get(api_url, params=params, timeout=10)
        data = resp.json()
        print(f"Status: {data.get('status')}")
        print(f"Message: {data.get('message')}")
        print(f"Result count: {len(data.get('result', [])) if isinstance(data.get('result'), list) else 'N/A'}")
        if data.get('status') == '0':
            print(f"Error Raw: {data.get('result')}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    # PEPE
    debug_api("0x6982508145454Ce325dDbE47a25d4ec3d2311933")
