"""Tests de dashboard/trading_safety.py (Fase 2)."""
from unittest.mock import patch, MagicMock

from django.test import override_settings

from dashboard.models import GlobalSettings
from dashboard.trading_safety import kill_switch_active, new_client_order_id
from .base import SQLiteTestCase


class KillSwitchActiveTests(SQLiteTestCase):
    """kill_switch_active() es fail-closed."""

    def test_flag_off(self):
        GlobalSettings.objects.create(id=1, kill_switch_active=False)
        self.assertFalse(kill_switch_active())

    def test_flag_on(self):
        GlobalSettings.objects.create(id=1, kill_switch_active=True)
        self.assertTrue(kill_switch_active())

    def test_no_row_creates_and_returns_false(self):
        # get_or_create crea la fila con default False
        self.assertFalse(kill_switch_active())
        self.assertTrue(GlobalSettings.objects.filter(id=1).exists())

    @patch('dashboard.models.GlobalSettings.objects.get_or_create',
           side_effect=Exception('DB caída'))
    def test_db_error_fails_closed(self, mock_gs):
        self.assertTrue(kill_switch_active())


class NewClientOrderIdTests(SQLiteTestCase):
    """Formato del clientOrderId para Binance."""

    def test_format(self):
        cid = new_client_order_id('cdash_sb', 7)
        self.assertTrue(cid.startswith('cdash_sb7_'))
        # Binance: máx 36 chars, solo letras/dígitos/underscore
        self.assertLessEqual(len(cid), 36)
        self.assertTrue(all(c.isalnum() or c == '_' for c in cid))

    def test_unique(self):
        ids = {new_client_order_id('cdash_lb', 1) for _ in range(50)}
        self.assertEqual(len(ids), 50)
