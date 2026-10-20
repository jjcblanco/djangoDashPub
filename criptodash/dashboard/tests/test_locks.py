"""Tests de locks del ciclo de trading (Fase 2)."""
from unittest.mock import patch

from django.core.cache import cache

from dashboard.bot_manager import BotManager
from .base import SQLiteTestCase


class CycleLockTests(SQLiteTestCase):
    """Lock global del ciclo LiveBot (trading:live_cycle_lock)."""

    def tearDown(self):
        cache.clear()

    @patch('dashboard.bot_manager.BotManager.check_global_risk', return_value=True)
    def test_lock_blocks_concurrent_cycle(self, mock_risk):
        cache.set('trading:live_cycle_lock', '1', timeout=300)
        result = BotManager.update_all_active_bots()
        self.assertEqual(result, [])  # ciclo omitido por lock activo

    @patch('dashboard.bot_manager.BotManager.check_global_risk', return_value=True)
    def test_lock_released_after_cycle(self, mock_risk):
        result = BotManager.update_all_active_bots()
        # Sin bots activos retorna [] pero libera el lock
        self.assertEqual(result, [])
        self.assertIsNone(cache.get('trading:live_cycle_lock'))

    @patch('dashboard.models.GlobalSettings.objects.get_or_create',
           side_effect=Exception('DB error'))
    def test_risk_fail_closed_stops_cycle(self, mock_gs):
        """Fase 2: check_global_risk fail-closed → ante error devuelve False."""
        self.assertFalse(BotManager.check_global_risk())


class ScalpBotLockTests(SQLiteTestCase):
    """Lock por bot scalping (scalp:bot_lock:{id}) vía cache.add atómico."""

    def tearDown(self):
        cache.clear()

    def test_cache_add_atomic(self):
        key = 'scalp:bot_lock:42'
        first = cache.add(key, '1', timeout=120)
        second = cache.add(key, '1', timeout=120)
        self.assertTrue(first)
        self.assertFalse(second)
        cache.delete(key)
        self.assertTrue(cache.add(key, '1', timeout=120))
