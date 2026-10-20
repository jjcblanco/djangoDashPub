"""Tests del cierre seguro de trades (Fase 2): CLOSE_FAILED sin tocar balance."""
from decimal import Decimal
from unittest.mock import patch

from dashboard.bot_manager import BotManager
from dashboard.models import Exchange, LiveBot, LiveTrade, TradingPair
from .base import SQLiteTestCase


class CloseTradeTests(SQLiteTestCase):

    def setUp(self):
        exchange = Exchange.objects.create(name='Binance')
        self.pair = TradingPair.objects.create(symbol='BTC/USDT', exchange=exchange)
        self.bot = LiveBot.objects.create(
            name='grid-test', pair=self.pair, strategy_type='GRID',
            initial_balance=Decimal('1000'), current_balance=Decimal('1000'),
            status='RUNNING', is_live=False,
            parameters={'timeframe': '1h', 'grid_levels': 5, 'amount_per_level': 10},
        )
        self.trade = LiveTrade.objects.create(
            bot=self.bot, side='BUY', entry_price=Decimal('100'),
            amount=Decimal('1'), status='OPEN',
        )

    def test_sim_close_updates_pnl_and_balance(self):
        """SIM: cierre calcula PnL y suma revenue al balance."""
        BotManager._close_trade(self.trade, 110, 'GRID_LIMIT_TP')
        self.trade.refresh_from_db()
        self.bot.refresh_from_db()
        self.assertEqual(self.trade.status, 'CLOSED')
        self.assertAlmostEqual(float(self.trade.pnl), 9.79, places=2)  # 10 - 0.21 comisión
        self.assertGreater(float(self.bot.current_balance), 1000)

    @patch('dashboard.bot_manager.exchange.create_order',
           side_effect=Exception('Binance timeout'))
    def test_live_close_failure_marks_close_failed(self, mock_order):
        """LIVE: si la venta real falla → CLOSE_FAILED, balance intacto."""
        self.bot.is_live = True
        self.bot.save()
        balance_before = self.bot.current_balance

        BotManager._close_trade(self.trade, 110, 'GRID_LIMIT_TP')

        self.trade.refresh_from_db()
        self.bot.refresh_from_db()
        self.assertEqual(self.trade.status, 'CLOSE_FAILED')
        self.assertIsNotNone(self.trade.exit_client_order_id)
        self.assertEqual(self.bot.current_balance, balance_before)
        self.assertEqual(self.trade.pnl, Decimal('0'))
        self.assertTrue(self.bot.last_error)

    @patch('dashboard.bot_manager.exchange.create_order',
           return_value={'id': 'binance-123'})
    def test_live_close_success_closes(self, mock_order):
        """LIVE: venta OK → CLOSED con exit_order_id y balance actualizado."""
        self.bot.is_live = True
        self.bot.save()

        BotManager._close_trade(self.trade, 110, 'GRID_LIMIT_TP')

        self.trade.refresh_from_db()
        self.bot.refresh_from_db()
        self.assertEqual(self.trade.status, 'CLOSED')
        self.assertEqual(self.trade.exit_order_id, 'binance-123')
        self.assertGreater(float(self.bot.current_balance), 1000)
        # clientOrderId fue enviado a Binance
        params = mock_order.call_args[1].get('params', {})
        self.assertIn('newClientOrderId', params)

    def test_active_trades_include_close_failed_no_bootstrap(self):
        """CLOSE_FAILED cuenta como trade activo: el grid no re-bootstrapea."""
        self.trade.status = 'CLOSE_FAILED'
        self.trade.save()
        from dashboard.bot_manager import LiveTrade as LT
        self.assertTrue(
            LT.objects.filter(bot=self.bot,
                              status__in=['OPEN', 'WAITING', 'CLOSE_FAILED']).exists()
        )
