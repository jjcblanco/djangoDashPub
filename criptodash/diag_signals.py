import os
import django
import pandas as pd
import sys

# Setup Django
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')
django.setup()

from dashboard.models import TradeSignal
from dashboard.data_service import generar_grafico_desde_señales

def test_signal_visibility():
    # Obtener señales de la DB
    señales = TradeSignal.objects.all().order_by('-timestamp')
    if not señales.exists():
        print("No hay señales en la DB para probar.")
        return

    # Convertir a DataFrame como hace la vista
    df = pd.DataFrame(list(señales.values('timestamp', 'signal_type', 'price', 'strength')))
    
    print(f"Total señales: {len(df)}")
    print(f"Tipos detectados: {df['signal_type'].unique()}")
    
    # Simular lógica de filtrado
    signal_col = 'signal_type'
    buys  = df[df[signal_col].str.lower() == 'buy']
    sells = df[df[signal_col].str.lower() == 'sell']
    
    print(f"Buys filtrados: {len(buys)}")
    print(f"Sells filtrados: {len(sells)}")
    
    if len(sells) > 0:
        print("Ejemplo de sell:")
        print(sells.iloc[0])
    else:
        print("ADVERTENCIA: No se encontraron señales de SELL con .str.lower() == 'sell'")

if __name__ == "__main__":
    test_signal_visibility()
