"""Tests de precios históricos en ShadowTrades (Fase ballenas)."""
from decimal import Decimal
from unittest.mock import patch

from django.utils import timezone

from dashboard.models import Exchange, TradingPair, WhaleWallet, ShadowTrade
from dashboard.whale.pipeline import PatternEngine
from .base import SQLiteTestCase


class WhalePricingTests(SQLiteTestCase):

    def setUp(self):
        self.wallet = WhaleWallet.objects.create(
            address='wallet-test-123', blockchain='ethereum', is_active=True,
        )

    def _fake_tx(self, raw_data):
        """Crea una WhaleTransaction falsa con timestamp fijo."""
        from dashboard.models import WhaleTransaction
        return WhaleTransaction.objects.create(
            wallet=self.wallet,
            tx_hash=f'tx-{timezone.now().timestamp()}-{hash(str(raw_data)) & 0xffff}',
            timestamp=timezone.now(),
            tx_type='SWAP',
            raw_data=raw_data,
        )

    @patch('dashboard.whale.context.fetch_market_context_at')
    @patch('dashboard.whale.analysis.WhaleAnalysisEngine.get_predictive_score', return_value=0.5)
    def test_entry_uses_historical_price_when_no_priceusd(self, mock_score, mock_ctx):
        """Sin priceUsd/px → el entry price viene del contexto histórico (no el actual)."""
        mock_ctx.return_value = {'price': 1.23, 'rsi_14': 50}
        tx = self._fake_tx({'no_price_here': True})

        with patch('dashboard.whale.context.fetch_market_context',
                   return_value={'rsi_14': 50, 'price': 999.0}):  # precio ACTUAL alto
            with patch('dashboard.whale.pipeline.PatternEngine.verify_token_security', return_value=True):
                PatternEngine._automated_shadow_trade(self.wallet, 'TEST', tx)

        trade = ShadowTrade.objects.filter(wallet=self.wallet, token_symbol='TEST').first()
        self.assertIsNotNone(trade)
        # 1.23 (histórico) y NO 999.0 (actual)
        self.assertEqual(float(trade.entry_price), 1.23)

    @patch('dashboard.whale.context.fetch_market_context_at')
    def test_close_uses_historical_price(self, mock_ctx):
        """Sin priceUsd/px en la tx de salida → exit usa el contexto histórico."""
        mock_ctx.return_value = {'price': 2.50, 'rsi_14': 60}
        trade = ShadowTrade.objects.create(
            wallet=self.wallet, token_symbol='TEST', entry_price=Decimal('2.0'),
            amount=Decimal('1'), status='OPEN',
        )
        tx = self._fake_tx({'no_price_here': True})

        with patch('dashboard.whale.pipeline.PatternEngine._update_whale_dna'):
            PatternEngine._close_shadow_trade(self.wallet, 'TEST', tx)

        trade.refresh_from_db()
        self.assertEqual(trade.status, 'CLOSED')
        self.assertEqual(float(trade.exit_price), 2.50)
        # PnL = (2.50 - 2.0) / 2.0 * 100 = 25%
        self.assertAlmostEqual(float(trade.pnl_percent), 25.0, places=2)

    @patch('dashboard.whale.context.fetch_market_context_at', return_value=None)
    @patch('dashboard.whale.pipeline._fetch_current_price', return_value=1.5)
    def test_fallback_to_current_price_when_no_historical(self, mock_current, mock_ctx):
        """Si no hay contexto histórico → cae al precio actual (comportamiento previo)."""
        tx = self._fake_tx({'no_price_here': True})

        with patch('dashboard.whale.context.fetch_market_context',
                   return_value={'rsi_14': 50}):
            with patch('dashboard.whale.analysis.WhaleAnalysisEngine.get_predictive_score', return_value=0.5):
                with patch('dashboard.whale.pipeline.PatternEngine.verify_token_security', return_value=True):
                    PatternEngine._automated_shadow_trade(self.wallet, 'TEST', tx)

        trade = ShadowTrade.objects.filter(wallet=self.wallet, token_symbol='TEST').first()
        self.assertIsNotNone(trade)
        self.assertEqual(float(trade.entry_price), 1.5)


class WhalePatternSignalTests(SQLiteTestCase):
    """generate_signal emite BUY cuando patrones activos matchean el contexto."""

    def setUp(self):
        from dashboard.models import WhalePattern
        WhalePattern.objects.create(
            pattern_name='rsi_bajo_gana',
            conditions={'rsi_14__lt': 40},
            timeframe='4h',
            sample_size=15,
            win_rate=0.8,
            is_active=True,
        )

    def test_signal_buy_on_match(self):
        from dashboard.whale.learner import WhalePatternLearner
        result = WhalePatternLearner.generate_signal('TEST', {'rsi_14': 32})
        self.assertEqual(result['signal'], 'BUY')
        self.assertGreater(result['confidence'], 0.6)
        self.assertEqual(len(result['matched_patterns']), 1)

    def test_hold_without_match(self):
        from dashboard.whale.learner import WhalePatternLearner
        result = WhalePatternLearner.generate_signal('TEST', {'rsi_14': 70})
        self.assertEqual(result['signal'], 'HOLD')
        self.assertEqual(result['matched_patterns'], [])

    def test_hold_with_empty_context(self):
        from dashboard.whale.learner import WhalePatternLearner
        result = WhalePatternLearner.generate_signal('TEST', None)
        self.assertEqual(result['signal'], 'HOLD')
