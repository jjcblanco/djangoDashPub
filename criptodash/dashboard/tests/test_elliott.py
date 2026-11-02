"""Tests del motor de ondas de Elliott (dashboard.elliott).

Usa datos sintéticos con secuencias impulsivas/correctivas construidas según
las proporciones clásicas de Fibonacci para validar la detección, las reglas
y las proyecciones sin depender de datos de mercado.
"""
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

import pandas as pd
from django.contrib.auth.models import User

from dashboard.elliott import analyze_elliott, detect_waves, _zigzag

from .base import SQLiteTestCase


def _df_from_levels(levels, bars_per_wave=15, base_ts=None):
    """Construye un DataFrame OHLCV caminando linealmente entre niveles."""
    base_ts = base_ts or datetime(2024, 1, 1)
    ts = base_ts
    rows = []
    for i in range(len(levels) - 1):
        start, end = levels[i], levels[i + 1]
        for j in range(bars_per_wave):
            t = j / (bars_per_wave - 1)
            close = start + (end - start) * t
            open_ = start + (end - start) * (j / bars_per_wave)
            high = max(open_, close) * 1.0003
            low = min(open_, close) * 0.9997
            rows.append({
                'timestamp': ts, 'open': open_, 'high': high,
                'low': low, 'close': close, 'volume': 100.0,
            })
            ts += timedelta(hours=1)
    return pd.DataFrame(rows)


def _add_ripple(df, amplitude_pct=0.4, period=4):
    """Añade un ripple senoidal al OHLC para simular ruido de mercado."""
    import numpy as np
    df = df.copy()
    i = np.arange(len(df))
    ripple = np.sin(i * 2 * np.pi / period) * amplitude_pct / 100
    for col in ('open', 'high', 'low', 'close'):
        df[col] = df[col] * (1 + ripple)
    return df


def _bullish_impulse_df():
    """Impulso alcista perfecto: W1=10, W2=0.618, W3=1.618, W4=0.382, W5=1.0."""
    p0 = 100.0
    p1 = p0 + 10.0                       # onda 1
    p2 = p1 - 10.0 * 0.618               # onda 2 (retroceso 0.618)
    p3 = p2 + 10.0 * 1.618               # onda 3 (extensión 1.618)
    p4 = p3 - (p3 - p2) * 0.382          # onda 4 (retroceso 0.382 de W3)
    p5 = p4 + 10.0 * 1.0                 # onda 5 (extensión 1.0 de W1)
    # Descenso previo para anclar el pivote inicial y declive posterior para cerrar el pico
    levels = [103.0, p0, p1, p2, p3, p4, p5, p5 * 0.99]
    return _df_from_levels(levels)


def _bearish_impulse_df():
    """Impulso bajista perfecto: espejo del alcista."""
    p0 = 100.0
    p1 = p0 - 10.0
    p2 = p1 + 10.0 * 0.5                 # retroceso 0.5
    p3 = p2 - 10.0 * 1.618
    p4 = p3 + (p2 - p3) * 0.382
    p5 = p4 - 10.0 * 1.0
    levels = [97.0, p0, p1, p2, p3, p4, p5, p5 * 1.01]
    return _df_from_levels(levels)


class ZigzagTests(unittest.TestCase):

    def test_zigzag_alternates_types(self):
        df = _bullish_impulse_df()
        pivots = _zigzag(df, depth=5, min_move_pct=0.5)
        self.assertGreaterEqual(len(pivots), 6)
        for a, b in zip(pivots, pivots[1:]):
            self.assertNotEqual(a['type'], b['type'], 'el zigzag debe alternar máximos/mínimos')

    def test_zigzag_filters_noise(self):
        # añadir ruido (ripple ±0.6%, período 12 barras) para crear pivotes falsos
        df = _add_ripple(_bullish_impulse_df(), amplitude_pct=0.6, period=12)
        all_pivots = _zigzag(df, depth=5, min_move_pct=0)
        few_pivots = _zigzag(df, depth=5, min_move_pct=3.0)
        self.assertGreater(len(all_pivots), len(few_pivots),
                           'el filtro min_move debe eliminar pivotes de ruido')


class ImpulseDetectionTests(unittest.TestCase):

    def test_detects_bullish_impulse(self):
        analysis = analyze_elliott(_bullish_impulse_df())
        self.assertEqual(analysis['structure'], 'impulse')
        self.assertEqual(analysis['bias'], 'bullish')
        self.assertGreaterEqual(analysis['confidence'], 90)
        rules = analysis['rules']
        self.assertTrue(rules['w2_retrace_ok'])
        self.assertTrue(rules['w3_not_shortest'])
        self.assertTrue(rules['w4_no_overlap'])
        labels = [w['label'] for w in analysis['waves']]
        self.assertEqual(labels, ['0', 'W1', 'W2', 'W3', 'W4', 'W5'])

    def test_detects_bearish_impulse(self):
        analysis = analyze_elliott(_bearish_impulse_df())
        self.assertEqual(analysis['structure'], 'impulse')
        self.assertEqual(analysis['bias'], 'bearish')
        self.assertGreaterEqual(analysis['confidence'], 90)
        self.assertTrue(analysis['rules']['w4_no_overlap'])

    def test_fib_ratios_match_synthetic(self):
        analysis = analyze_elliott(_bullish_impulse_df())
        fibs = analysis['fibs']
        self.assertAlmostEqual(fibs['w2_retrace'], 0.618, delta=0.05)
        self.assertAlmostEqual(fibs['w3_ext'], 1.618, delta=0.05)
        self.assertAlmostEqual(fibs['w4_retrace'], 0.382, delta=0.05)
        self.assertAlmostEqual(fibs['w5_ext'], 1.0, delta=0.05)
        # todos los ratios deben "pegar" en niveles ideales
        self.assertTrue(all(analysis['fib_hits'].values()))

    def test_projections_and_invalidation(self):
        analysis = analyze_elliott(_bullish_impulse_df())
        self.assertGreaterEqual(len(analysis['projections']), 3)
        p4_price = [w for w in analysis['waves'] if w['label'] == 'W4'][0]['price']
        inv = analysis['invalidation']
        self.assertIsNotNone(inv)
        # objetivos alcistas por encima del fin de la onda 4
        for t in analysis['projections']:
            self.assertGreater(t['price'], p4_price)
        self.assertLess(inv['price'], p4_price)


class LegacyInterfaceTests(unittest.TestCase):

    def test_detect_waves_shape(self):
        waves = detect_waves(_bullish_impulse_df(), order=5)
        self.assertTrue(waves)
        for w in waves:
            self.assertIn('timestamp', w)
            self.assertIn('price', w)
            self.assertIn('label', w)
            self.assertIn('type', w)
        labels = [w['label'] for w in waves]
        self.assertEqual(labels, ['0', 'W1', 'W2', 'W3', 'W4', 'W5'])


class EdgeCaseTests(unittest.TestCase):

    def test_insufficient_data(self):
        df = _df_from_levels([100, 101, 102, 103], bars_per_wave=3)
        analysis = analyze_elliott(df)
        self.assertEqual(analysis['structure'], 'indeterminate')
        self.assertEqual(analysis['status'], 'error')

    def test_empty_dataframe(self):
        analysis = analyze_elliott(pd.DataFrame())
        self.assertEqual(analysis['structure'], 'indeterminate')
        self.assertEqual(analysis['status'], 'error')

    def test_flat_market_no_structure(self):
        # Mercado sin tendencia: el filtro de ruido descarta todo → sin estructura
        base_ts = datetime(2024, 1, 1)
        rows = []
        ts = base_ts
        close = 100.0
        for i in range(200):
            close = 100.0 + ((i % 7) - 3) * 0.05  # ruido sin tendencia (±0.15%)
            rows.append({'timestamp': ts, 'open': close, 'high': close * 1.001,
                         'low': close * 0.999, 'close': close, 'volume': 100.0})
            ts += timedelta(hours=1)
        analysis = analyze_elliott(pd.DataFrame(rows))
        self.assertEqual(analysis['structure'], 'indeterminate')
        self.assertEqual(analysis['confidence'], 0.0)


class ElliottViewTests(SQLiteTestCase):
    """Validación end-to-end de la vista y el template (sin llamadas a Binance)."""

    def setUp(self):
        self.user = User.objects.create_user(username='elliott-test', password='test-pass')
        self.client.force_login(self.user)

    @patch('dashboard.views.elliott_views.DataManager.get_or_fetch')
    def test_page_renders_impulse(self, mock_fetch):
        mock_fetch.return_value = _bullish_impulse_df()
        resp = self.client.get('/elliott/', {'pair': 'BTC/USDT', 'timeframe': '4h'})
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode()
        self.assertIn('Elliott Wave Analyzer', content)
        self.assertIn('IMPULSO 1-2-3-4-5', content)
        self.assertIn('W5', content)
        self.assertIn('Reglas de Elliott', content)
        self.assertIn('Proyecciones / Objetivos', content)
        # el gráfico plotly debe estar embebido
        self.assertIn('plotly', content)

    @patch('dashboard.views.elliott_views.DataManager.get_or_fetch')
    def test_page_renders_error_state(self, mock_fetch):
        mock_fetch.return_value = pd.DataFrame()
        resp = self.client.get('/elliott/')
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode()
        self.assertIn('No se pudieron obtener datos', content)
        self.assertNotIn('IMPULSO', content)

    def test_requires_login(self):
        self.client.logout()
        resp = self.client.get('/elliott/')
        self.assertIn(resp.status_code, (302, 301))
        self.assertIn('login', resp.url)


if __name__ == '__main__':
    unittest.main()
