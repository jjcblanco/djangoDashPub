#!/usr/bin/env python3
import os                                                     t     import requests                                                
                                                                    
     def test_etherscan():                                          
         key = os.environ.get('ETH_API_KEY')                        
         if not key:                                                
             print("❌  ETH_API_KEY not in environment")           t             return False
                                                                 
         # Test with Vitalik's address
         url = "https://api.etherscan.io/api"
         params = {                                                 
             'module': 'account',
             'action': 'tokentx',
             'address': '0x742d35Cc6634C0532925a3b844Bc9e90F1b6f1d6',                  
             'page': 1,                                             
             'offset': 1,                                           
             'apikey': key                                          
         }                                                          
        try:
             resp = requests.get(url, params=params, timeout=10) 
             data = resp.json()
             if data.get('status') == '1':
                 print(f"✅  Etherscan API working: {len(data.get('result', []))} transactions")
                 return True
             else:
                 print(f"❌2 Etherscan error: {data.get('message', 'Unknown')}")                                                  
                 return False                                       
         except Exception as e:                                     
             print(f"❌  Connection error: {e}")                    
             return False                                          t     
     def test_env():
         print("🔍 Environment check:")
         keys = ['ETH_API_KEY', 'BASE_API_KEY', 'BINANCE_APIKEY'] 
         for key in keys:      
            value = os.environ.get(key)                            
            if value: 
                print(f"  ✅  {key}: {value[:8]}...")             t             
            else:
                print(f"  ❌  {key}: NOT SET")                     
                                                                    
     if __name__ == '__main__':                                     
         test_env()                                                 
         print()                                                   t         test_etherscan()  