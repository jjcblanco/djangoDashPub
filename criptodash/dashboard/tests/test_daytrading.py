"""Tests de la estrategia DayTrading fusionada y el guard de live (Fase 2/2b)."""
from decimal import Decimal

import pandas as pd
import numpy as np

from dashboard.backtester import DayTradingStrategy
from dashboard.bot_manager import BotManager
from dashboard.models import Exchange, LiveBot, LiveTrade, TradingPair
from .base import SQLiteTestCase


class NormalizeParametersTests(SQLiteTestCase):
    """Params legacy (EMA Ribbon) se traducen a los de la estrategia optimizada."""

    def test_legacy_keys_translated(self):
        s = DayTradingStrategy(parameters={
            'min_strength': 4, 'atr_sl': 1.5, 'atr_tp': 3.0,
            'rsi_buy': 55, 'rsi_sell': 45, 'ema_med': 21,
            'strategy_mode': 'balanced',
        })
        p = s.parameters
        self.assertEqual(p['atr_sl_multiplier'], 1.5)
        self.assertEqual(p['atr_tp_multiplier'], 3.0)
        self.assertEqual(p['rsi_upper_static'], 55)
        self.assertEqual(p['rsi_lower_static'], 45)
        self.assertEqual(p['ema_slow'], 21)
        # claves legacy eliminadas
        for key in ('min_strength', 'atr_sl', 'atr_tp', 'rsi_buy', 'rsi_sell',
                    'ema_med', 'strategy_mode'):
            self.assertNotIn(key, p)

    def test_optimized_keys_pass_through(self):
        s = DayTradingStrategy(parameters={'atr_sl_multiplier': 2.5, 'cooldown_bars': 7})
        self.assertEqual(s.parameters['atr_sl_multiplier'], 2.5)
        self.assertEqual(s.parameters['cooldown_bars'], 7)

    def test_strings_cast_to_numbers(self):
        s = DayTradingStrategy(parameters={'ema_fast': '9', 'atr_sl_multiplier': '1.5'})
        self.assertEqual(s.parameters['ema_fast'], 9)
        self.assertEqual(s.parameters['atr_sl_multiplier'], 1.5)


class GenerateSignalsTests(SQLiteTestCase):

    def _synthetic_df(self, n=400, trend=0.5):
        np.random.seed(42)
        close = 100 + np.cumsum(np.random.randn(n) * 0.5 + trend * 0.1)
        return pd.DataFrame({
            'open': close + np.random.randn(n) * 0.2,
            'high': close + abs(np.random.randn(n)) * 0.6,
            'low': close - abs(np.random.randn(n)) * 0.6,
            'close': close,
            'volume': np.random.rand(n) * 1000 + 500,
        })

    def test_output_columns(self):
        out = DayTradingStrategy().generate_signals(self._synthetic_df())
        for col in ('signal', 'stop_loss', 'take_profit', 'signal_strength'):
            self.assertIn(col, out.columns)
        self.assertTrue(set(out['signal'].unique()) <= {'HOLD', 'BUY', 'SELL'})

    def test_trending_market_generates_signals(self):
        out = DayTradingStrategy().generate_signals(self._synthetic_df(trend=0.8))
        self.assertIn('BUY', out['signal'].values)


class DaytradingLiveGuardTests(SQLiteTestCase):
    """DAYTRADING con is_live=True queda bloqueado (Fase 2)."""

    def test_live_bot_blocked(self):
        exchange = Exchange.objects.create(name='Binance')
        pair = TradingPair.objects.create(symbol='ETH/USDT', exchange=exchange)
        bot = LiveBot.objects.create(
            name='day-live', pair=pair, strategy_type='DAYTRADING',
            initial_balance=Decimal('500'), current_balance=Decimal('500'),
            status='RUNNING', is_live=True, parameters={'timeframe': '1h'},
        )
        df = pd.DataFrame({'close': [100.0] * 50})
        result = BotManager._manage_daytrading_bot(bot, df)
        self.assertEqual(result.get('error'), 'daytrading_live_blocked')
        bot.refresh_from_db()
        self.assertEqual(bot.status, 'ERROR')
        self.assertIn('no soportado', bot.last_error)
        # No se creó ningún trade
        self.assertFalse(LiveTrade.objects.filter(bot=bot).exists())
