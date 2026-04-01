import requests
import json

def discover_token_whales(contract_address, blockchain='ethereum', api_key=""):
    """
    Versión standalone de la lógica de Whale Scout para prueba inmediata.
    """
    api_urls = {
        'ethereum': 'https://api.etherscan.io/api',
        'base': 'https://api.basescan.org/api',
    }
    api_url = api_urls.get(blockchain, api_urls['ethereum'])
    
    params = {
        'module': 'account',
        'action': 'tokentx',
        'contractaddress': contract_address,
        'sort': 'desc',
        'page': 1,
        'offset': 50,
        'apikey': api_key
    }
    
    try:
        resp = requests.get(api_url, params=params, timeout=12)
        if resp.status_code != 200: 
            print(f"❌ Error HTTP: {resp.status_code}")
            return []
        
        data = resp.json()
        if data.get('status') != '1':
            print(f"❌ Error API: {data.get('message')}")
            return []
        
        transfers = data.get('result', [])
        buyers = {} 
        
        for tx in transfers:
            to_addr = tx.get('to', '').lower()
            if to_addr in ('0x0000000000000000000000000000000000000000', '0x000000000000000000000000000000000000dead'):
                continue
            
            try:
                amount = float(tx.get('value', 0)) / (10**int(tx.get('tokenDecimal', 18)))
            except: amount = 0
            
            symbol = tx.get('tokenSymbol', '???')
            if to_addr not in buyers:
                buyers[to_addr] = {'volume': 0, 'tx_count': 0, 'symbol': symbol, 'address': to_addr}
            
            buyers[to_addr]['volume'] += amount
            buyers[to_addr]['tx_count'] += 1
        
        sorted_buyers = sorted(buyers.values(), key=lambda x: x['volume'], reverse=True)
        return sorted_buyers[:5]
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return []

if __name__ == "__main__":
    # PEPE Token on ETH
    pepe = "0x6982508145454Ce325dDbE47a25d4ec3d2311933"
    # Usar API Key de Ethereum si está disponible, sino vacía para demo (límite 5s)
    res = discover_token_whales(pepe, 'ethereum')
    
    print(f"--- 📡 MUESTRA DE DESCUBRIMIENTO (WHALE SCOUT) ---")
    if res:
        for i, w in enumerate(res, 1):
            print(f"{i}. Wallet: {w['address'][:10]}... | Acumulado: {w['volume']:,.0f} {w['symbol']}")
    else:
        print("No se encontraron resultados (Límite de API gratuito o contrato inactivo).")
