"""Tests de protección de vistas (login_required en rutas críticas)."""
from django.urls import reverse

from .base import SQLiteTestCase


class LoginRequiredTests(SQLiteTestCase):
    """Vistas críticas redirigen anónimos al login."""

    PROTECTED = [
        ('bot_dashboard', None),            # /bots/
        ('scalping_dashboard', None),       # /scalping/
        ('range_scanner', None),            # /range-scanner/
        ('trend_scanner', None),            # /trend-scanner/
        ('backtest', None),                 # /backtest/
        ('whale_insights', None),           # /whale-insights/
    ]

    def test_anonymous_redirected_to_login(self):
        for url_name, kwargs in self.PROTECTED:
            url = reverse(url_name, kwargs=kwargs) if kwargs else reverse(url_name)
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302, f'{url_name} no redirige')
            self.assertIn('/accounts/login/', response.url)

    def test_public_pages_load(self):
        """Login y landing (index) son públicas."""
        for url_name in ('custom_login', 'dashboard_index'):
            response = self.client.get(reverse(url_name))
            self.assertEqual(response.status_code, 200)
