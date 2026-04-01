import requests
import json

def test_logs(contract_address, blockchain='ethereum', api_key=""):
    api_urls = {
        'ethereum': 'https://api.etherscan.io/api',
        'base': 'https://api.basescan.org/api',
    }
    api_url = api_urls.get(blockchain, api_urls['ethereum'])
    
    # Topic 0 para Transfer (indexado)
    # Transfer (index_topic_1 address from, index_topic_2 address to, uint256 value)
    TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
    
    params = {
        'module': 'logs',
        'action': 'getLogs',
        'fromBlock': '0', # O algún bloque reciente para velocidad
        'toBlock': 'latest',
        'address': contract_address,
        'topic0': TRANSFER_TOPIC,
        'apikey': api_key
    }
    
    print(f"--- 📡 Probando getLogs para {contract_address} ---")
    try:
        resp = requests.get(api_url, params=params, timeout=10)
        data = resp.json()
        print(f"Status: {data.get('status')}")
        print(f"Message: {data.get('message')}")
        logs = data.get('result', [])
        print(f"Logs found: {len(logs)}")
        
        if logs:
            first = logs[0]
            # topic1: from, topic2: to, data: value
            from_addr = "0x" + first['topics'][1][-40:]
            to_addr = "0x" + first['topics'][2][-40:]
            value = int(first['data'], 16)
            print(f"Sample: From {from_addr} To {to_addr} Value {value}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    # PEPE
    test_logs("0x6982508145454Ce325dDbE47a25d4ec3d2311933")
