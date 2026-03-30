import os
import django
import sys
from datetime import timedelta
from django.utils import timezone

sys.path.append(r'C:\Users\Javier\Desktop\programacion\djangoDashPub\criptodash')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')
django.setup()

from dashboard.models import WhaleWallet, ShadowTrade
from dashboard.services import PatternEngine

# 1. Obtener una ballena de prueba
wallet = WhaleWallet.objects.filter(is_active=True).first()
if not wallet:
    print("No active wallets found.")
    sys.exit()

print(f"Testing DNA for {wallet.name or wallet.address}...")

# 2. Asegurarnos de que tenga un trade OPEN con contexto
trade = ShadowTrade.objects.filter(wallet=wallet, status='OPEN').first()
if not trade:
    # Crear uno si no hay
    trade = ShadowTrade.objects.create(
        wallet=wallet,
        token_symbol='SOL',
        entry_price=150.0,
        amount=1.0,
        status='OPEN',
        market_context={'rsi_14': 35.5, 'in_uptrend': True}
    )
    # Retroceder la fecha de creacion para simular holding time (requiere save manual de created_at si no es auto_now_add)
    # Pero como es auto_now_add, usaremos closed_at en el futuro
    print("Created dummy OPEN trade.")

# 3. Simular un cierre (SELL) vía Mock Transaction
class MockTx:
    def __init__(self, price, timestamp):
        self.raw_data = {'priceUsd': price}
        self.timestamp = timestamp

# Simular que vendió 2 horas después a un precio mayor
sell_time = timezone.now() + timedelta(hours=2)
mock_tx = MockTx(price=165.0, timestamp=sell_time)

print(f"Closing trade for {trade.token_symbol} at {mock_tx.raw_data['priceUsd']}...")
PatternEngine._close_shadow_trade(wallet, trade.token_symbol, mock_tx)

wallet.refresh_from_db()
print(f"Updated DNA: {wallet.trading_dna}")

if 'win_rate' in wallet.trading_dna:
    print("SUCCESS: DNA populated correctly!")
else:
    print("FAILURE: DNA empty.")
