"""Tests de detección de flujos CEX (depósitos/retiros hacia/desde exchanges)."""
from decimal import Decimal
from unittest.mock import patch

from django.utils import timezone

from dashboard.models import WhaleWallet, WhaleTransaction
from dashboard.whale.flows import (
    detect_exchange_flows, extract_counterparty, _decode_bsc_topic, ALERT_THRESHOLD_USD,
)
from dashboard.whale.constants import lookup_exchange_wallet
from .base import SQLiteTestCase


BINANCE_ETH = '0x28C6c06298d514Db089934071355E5743bf21d60'  # Binance 14
COINBASE_ETH = '0xA9D1e08C7793af67e9d92fe308d5697FB81d3E43'  # Coinbase 1
BINANCE_SOL = '5tzFkiKscXHK5ZXCGbXZxdw7gTjjD1mBwuoFbhUvuAi9'


class ConstantsTests(SQLiteTestCase):

    def test_lookup_binance_eth(self):
        hit = lookup_exchange_wallet(BINANCE_ETH)
        self.assertEqual(hit, ('ethereum', 'Binance'))

    def test_lookup_normalizes_case(self):
        hit = lookup_exchange_wallet(BINANCE_ETH.upper())
        self.assertEqual(hit, ('ethereum', 'Binance'))

    def test_lookup_unknown_returns_none(self):
        self.assertIsNone(lookup_exchange_wallet('0x0000000000000000000000000000000000000000'))


class BscTopicDecodeTests(SQLiteTestCase):

    def test_decode_32byte_topic(self):
        padded = '0x' + '0' * 24 + '8894e0a0c962cb723c1976a4421c95949be2d4e3'
        self.assertEqual(_decode_bsc_topic(padded), '0x8894e0a0c962cb723c1976a4421c95949be2d4e3')

    def test_decode_invalid(self):
        self.assertIsNone(_decode_bsc_topic('0x1234'))
        self.assertIsNone(_decode_bsc_topic(None))


class EvmFlowsTests(SQLiteTestCase):

    def setUp(self):
        self.wallet = WhaleWallet.objects.create(
            address='0x1111111111111111111111111111111111111111',
            blockchain='ethereum', is_active=True,
        )

    def _tx(self, tx_type, raw):
        return WhaleTransaction.objects.create(
            wallet=self.wallet,
            tx_hash=f"tx-{timezone.now().timestamp()}-{tx_type}-{len(raw)}",
            timestamp=timezone.now(),
            tx_type=tx_type,
            from_asset='SOL' if tx_type == 'SELL' else None,
            to_asset='SOL' if tx_type == 'BUY' else None,
            amount_in=Decimal('1000'),
            amount_out=Decimal('1000'),
            raw_data=raw,
        )

    @patch('dashboard.services.fetch_current_price', return_value=100.0)
    def test_sell_to_binance_hot_wallet_is_deposit(self, mock_price):
        tx = self._tx('SELL', {'from': self.wallet.address, 'to': BINANCE_ETH})
        flows = detect_exchange_flows(self.wallet, [tx])
        self.assertEqual(len(flows), 1)
        f = flows[0]
        self.assertEqual(f['exchange'], 'Binance')
        self.assertEqual(f['direction'], 'DEPOSIT')
        self.assertEqual(f['token_symbol'], 'SOL')
        self.assertEqual(f['usd_value'], 100000.0)  # 1000 SOL × $100

    @patch('dashboard.services.fetch_current_price', return_value=2.0)
    def test_buy_from_coinbase_is_withdrawal(self, mock_price):
        tx = self._tx('BUY', {'from': COINBASE_ETH, 'to': self.wallet.address})
        flows = detect_exchange_flows(self.wallet, [tx])
        self.assertEqual(len(flows), 1)
        f = flows[0]
        self.assertEqual(f['exchange'], 'Coinbase')
        self.assertEqual(f['direction'], 'WITHDRAWAL')
        self.assertEqual(f['usd_value'], 2000.0)

    def test_non_exchange_counterparty_ignored(self):
        tx = self._tx('SELL', {'from': self.wallet.address, 'to': '0x2222222222222222222222222222222222222222'})
        flows = detect_exchange_flows(self.wallet, [tx])
        self.assertEqual(flows, [])

    def test_dex_router_sell_is_not_cex_flow(self):
        # Un SELL cuyo 'to' es un router DEX (no hot wallet) no es flujo CEX
        router = '0x7a250d5630b4cf539739df2c5dacb4c659f2488d'  # Uniswap V2 router
        tx = self._tx('SELL', {'from': self.wallet.address, 'to': router})
        self.assertEqual(detect_exchange_flows(self.wallet, [tx]), [])


class BscFlowsTests(SQLiteTestCase):

    def setUp(self):
        self.wallet = WhaleWallet.objects.create(
            address='0x1111111111111111111111111111111111111111',
            blockchain='bsc', is_active=True,
        )

    def _tx(self, tx_type, from_addr, to_addr):
        topics = [None,
                  '0x' + '0' * 24 + from_addr.replace('0x', ''),
                  '0x' + '0' * 24 + to_addr.replace('0x', '')]
        return WhaleTransaction.objects.create(
            wallet=self.wallet,
            tx_hash=f"bsc-tx-{timezone.now().timestamp()}",
            timestamp=timezone.now(),
            tx_type=tx_type,
            from_asset='CAKE' if tx_type == 'SELL' else None,
            to_asset='CAKE' if tx_type == 'BUY' else None,
            amount_in=Decimal('500'),
            amount_out=Decimal('500'),
            raw_data={'topics': topics},
        )

    @patch('dashboard.services.fetch_current_price', return_value=5.0)
    def test_bsc_sell_to_binance_is_deposit(self, mock_price):
        tx = self._tx('SELL', self.wallet.address, '0x8894e0a0c962cb723c1976a4421c95949be2d4e3')
        flows = detect_exchange_flows(self.wallet, [tx])
        self.assertEqual(len(flows), 1)
        self.assertEqual(flows[0]['exchange'], 'Binance')
        self.assertEqual(flows[0]['direction'], 'DEPOSIT')


class SolanaFlowsTests(SQLiteTestCase):

    def setUp(self):
        self.wallet = WhaleWallet.objects.create(
            address='Whale11111111111111111111111111111111111111111',
            blockchain='solana', is_active=True,
        )

    @patch('dashboard.services.fetch_current_price', return_value=3.0)
    def test_solana_transfer_to_binance_hot_wallet(self, mock_price):
        tx = WhaleTransaction.objects.create(
            wallet=self.wallet,
            tx_hash=f"sol-tx-{timezone.now().timestamp()}",
            timestamp=timezone.now(),
            tx_type='SELL',
            from_asset='BONK',
            amount_in=Decimal('20000'),
            raw_data={
                'meta': {
                    'preTokenBalances': [
                        {'owner': self.wallet.address, 'mint': 'BONK', 'uiTokenAmount': {'uiAmount': 20000}},
                        {'owner': BINANCE_SOL, 'mint': 'BONK', 'uiTokenAmount': {'uiAmount': 0}},
                    ],
                    'postTokenBalances': [
                        {'owner': self.wallet.address, 'mint': 'BONK', 'uiTokenAmount': {'uiAmount': 0}},
                        {'owner': BINANCE_SOL, 'mint': 'BONK', 'uiTokenAmount': {'uiAmount': 20000}},
                    ],
                },
            },
        )
        flows = detect_exchange_flows(self.wallet, [tx])
        self.assertEqual(len(flows), 1)
        self.assertEqual(flows[0]['exchange'], 'Binance')
        self.assertEqual(flows[0]['direction'], 'DEPOSIT')


class AlertThresholdTests(SQLiteTestCase):
    """Umbral de alerta Telegram: ≥ $50k."""

    def test_threshold_constant(self):
        self.assertEqual(ALERT_THRESHOLD_USD, 50000)

    def test_small_flow_below_threshold(self):
        # Verificar que el valor USD calculado funciona para comparar con el umbral
        self.assertLess(49999.99, ALERT_THRESHOLD_USD)
        self.assertGreaterEqual(50000.0, ALERT_THRESHOLD_USD)
