import ccxt
import json
from decouple import config

def diagnose():
    print("Iniciando Diagnóstico de Binance...")
    exchange = ccxt.binance({
        'apiKey': config('BINANCE_APIKEY'),
        'secret': config('BINANCE_SECRET'),
        'enableRateLimit': True,
    })
    
    try:
        # 1. Verificar Balance
        balance = exchange.fetch_balance()
        usdt_free = balance['free'].get('USDT', 0)
        usdt_total = balance['total'].get('USDT', 0)
        print(f"Saldo USDT Total: {usdt_total}")
        print(f"Saldo USDT Libre: {usdt_free}")
        
        # 2. Verificar Filtros del Par (Ejemplo BTC/USDT)
        # Intentaré obtener el par que el bot está usando, pero como no lo sé, listaré los comunes.
        for symbol in ['BTC/USDT', 'ETH/USDT', 'SOL/USDT']:
            market = exchange.market(symbol)
            print(f"\nFiltros para {symbol}:")
            print(f" - Min Amount: {market['limits']['amount']['min']}")
            print(f" - Min Cost (Notional): {market['limits']['cost']['min']}")
            print(f" - Precision Amount: {market['precision']['amount']}")
            print(f" - Precision Price: {market['precision']['price']}")

    except Exception as e:
        print(f"Error en diagnóstico: {e}")

if __name__ == "__main__":
    diagnose()
