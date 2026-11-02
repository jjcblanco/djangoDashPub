"""
Motor de análisis de Ondas de Elliott.

Detecta secuencias impulsivas (1-2-3-4-5) y correctivas (A-B-C) sobre un zigzag
de pivotes calculado a partir de datos OHLC, valida las reglas clásicas y las
relaciones de Fibonacci, y calcula proyecciones, niveles de invalidación y un
score de confianza 0-100.

Reglas aplicadas (impulso):
  1. La onda 2 no retrocede más del 100% de la onda 1.
  2. La onda 3 nunca es la más corta entre las ondas 1, 3 y 5.
  3. La onda 4 no invade el territorio de precios de la onda 1 (no solapa).

Relaciones de Fibonacci evaluadas:
  - Retroceso de la onda 2 sobre la 1: 0.382 / 0.5 / 0.618
  - Extensión de la onda 3 sobre la 1: 1.0 / 1.618 / 2.0 / 2.618
  - Retroceso de la onda 4 sobre la 3: 0.236 / 0.382
  - Extensión de la onda 5 sobre la 1: 0.618 / 1.0 / 1.618
  - Correcciones: B sobre A (0.382 / 0.5 / 0.786) y C sobre A (0.618 / 1.0 / 1.618)

Sin dependencia de scipy: el zigzag se calcula con ventanas locales puras.
"""

import logging

import numpy as np
import pandas as pd
from plotly import graph_objs as go

logger = logging.getLogger(__name__)

# ── Parámetros de Fibonacci ──────────────────────────────────────────────
FIB_IDEAL_RETRACE_2 = [0.382, 0.5, 0.618]
FIB_IDEAL_EXT_3 = [1.0, 1.618, 2.0, 2.618]
FIB_IDEAL_RETRACE_4 = [0.236, 0.382]
FIB_IDEAL_W5 = [0.618, 1.0, 1.618]
FIB_IDEAL_B = [0.382, 0.5, 0.786]
FIB_IDEAL_C = [0.618, 1.0, 1.618]

FIB_TOLERANCE = 0.10  # ±10% de desviación respecto al nivel ideal
MIN_SCORE_IMPULSE = 55  # umbral de confianza para aceptar una estructura
MIN_SCORE_CORRECTION = 55

WAVE_COLORS = {
    '0': '#8b949e',
    'W1': '#fff176', 'W3': '#fff176', 'W5': '#fff176',
    'W2': '#ef9a9a', 'W4': '#ef9a9a',
    'A': '#f48fb1', 'B': '#80cbc4', 'C': '#f48fb1',
}


# ── Zigzag ───────────────────────────────────────────────────────────────

def _find_pivots(highs, lows, depth):
    """Índices de pivotes locales. Izquierda estricta y derecha no estricta
    para evitar pivotes duplicados en mesetas."""
    n = len(highs)
    pivot_highs, pivot_lows = [], []
    for i in range(depth, n - depth):
        if highs[i] > highs[i - depth:i].max() and highs[i] >= highs[i + 1:i + depth + 1].max():
            pivot_highs.append(i)
        if lows[i] < lows[i - depth:i].min() and lows[i] <= lows[i + 1:i + depth + 1].min():
            pivot_lows.append(i)
    return pivot_highs, pivot_lows


def _zigzag(df, depth=5, min_move_pct=0.5):
    """Zigzag de pivotes alternados con filtro de ruido (movimiento mínimo %)."""
    highs = df['high'].to_numpy(dtype=float)
    lows = df['low'].to_numpy(dtype=float)
    ts = df['timestamp'].to_numpy()
    closes = df['close'].to_numpy(dtype=float)

    pivot_highs, pivot_lows = _find_pivots(highs, lows, depth)

    pivots = []
    for idx in pivot_highs:
        pivots.append({'idx': int(idx), 'price': float(highs[idx]), 'type': 'high', 'ts': ts[idx]})
    for idx in pivot_lows:
        pivots.append({'idx': int(idx), 'price': float(lows[idx]), 'type': 'low', 'ts': ts[idx]})
    pivots.sort(key=lambda p: p['idx'])

    # Forzar alternancia: si dos pivotes consecutivos son del mismo tipo,
    # conservar el más extremo.
    alternated = []
    for p in pivots:
        if alternated and alternated[-1]['type'] == p['type']:
            prev = alternated[-1]
            if (p['type'] == 'high' and p['price'] > prev['price']) or \
               (p['type'] == 'low' and p['price'] < prev['price']):
                alternated[-1] = p
        else:
            alternated.append(p)

    # Filtro de ruido: descartar pivotes que se muevan menos de min_move_pct %
    if min_move_pct and min_move_pct > 0:
        kept = []
        for p in alternated:
            if not kept or abs(p['price'] - kept[-1]['price']) / kept[-1]['price'] * 100 >= min_move_pct:
                kept.append(p)
        alternated = kept

    return alternated


# ── Evaluación de secuencias ─────────────────────────────────────────────

def _near_ideal(ratio, ideals):
    """True si el ratio está dentro de FIB_TOLERANCE de algún nivel ideal."""
    return any(abs(ratio - ideal) <= FIB_TOLERANCE for ideal in ideals)


def _evaluate_impulse(seq, direction):
    """Evalúa 6 pivotes alternados como impulso de 5 ondas.

    direction = +1 alcista (arranca en mínimo), -1 bajista (arranca en máximo).
    Devuelve None si la secuencia no es geométricamente un impulso.
    """
    p = [s['price'] for s in seq]
    if direction > 0:
        w1, w2, w3, w4, w5 = p[1] - p[0], p[1] - p[2], p[3] - p[2], p[3] - p[4], p[5] - p[4]
        no_overlap = p[4] > p[1]  # onda 4 no entra en territorio de onda 1
    else:
        w1, w2, w3, w4, w5 = p[0] - p[1], p[2] - p[1], p[2] - p[3], p[4] - p[3], p[4] - p[5]
        no_overlap = p[4] < p[1]

    if w1 <= 0 or w3 <= 0 or w5 <= 0:
        return None

    ret2 = w2 / w1
    ret4 = w4 / w3
    ext3 = w3 / w1
    ext5 = w5 / w1

    rules = {
        'w2_retrace_ok': 0 < ret2 <= 1.0,
        'w3_not_shortest': w3 >= min(w1, w5),
        'w4_no_overlap': bool(no_overlap),
    }
    fibs = {
        'w2_retrace': round(ret2, 3),
        'w3_ext': round(ext3, 3),
        'w4_retrace': round(ret4, 3),
        'w5_ext': round(ext5, 3),
    }
    fib_hits = {
        'w2_retrace': _near_ideal(ret2, FIB_IDEAL_RETRACE_2),
        'w3_ext': _near_ideal(ext3, FIB_IDEAL_EXT_3),
        'w4_retrace': _near_ideal(ret4, FIB_IDEAL_RETRACE_4),
        'w5_ext': _near_ideal(ext5, FIB_IDEAL_W5),
    }

    score = sum(25 for ok in rules.values() if ok)
    score += sum(6.25 for ok in fib_hits.values() if ok)
    score = round(min(score, 100.0), 1)

    return {
        'score': score, 'rules': rules, 'fibs': fibs, 'fib_hits': fib_hits,
        'w1': w1, 'w2': w2, 'w3': w3, 'w4': w4, 'w5': w5,
    }


def _evaluate_correction(seq, direction):
    """Evalúa 4 pivotes alternados como corrección A-B-C.

    direction es la del impulso previo: +1 → corrección bajista (arranca en máximo).
    """
    p = [s['price'] for s in seq]
    if direction > 0:
        a, b, c = p[0] - p[1], p[2] - p[1], p[2] - p[3]
    else:
        a, b, c = p[1] - p[0], p[1] - p[2], p[3] - p[2]

    if a <= 0 or b <= 0 or c <= 0:
        return None

    fb = b / a
    fc = c / a

    rules = {'b_less_than_a': b < a}
    fibs = {'b_over_a': round(fb, 3), 'c_over_a': round(fc, 3)}
    fib_hits = {
        'b_over_a': _near_ideal(fb, FIB_IDEAL_B),
        'c_over_a': _near_ideal(fc, FIB_IDEAL_C),
    }

    score = 20.0 if rules['b_less_than_a'] else 0.0
    score += sum(40.0 for ok in fib_hits.values() if ok)
    score = round(min(score, 100.0), 1)

    return {'score': score, 'rules': rules, 'fibs': fibs, 'fib_hits': fib_hits,
            'a': a, 'b': b, 'c': c}


# ── Análisis principal ───────────────────────────────────────────────────

def _empty_result(reason):
    return {
        'status': 'error',
        'error': reason,
        'structure': 'indeterminate',
        'waves': [], 'zigzag': [], 'rules': {}, 'fibs': {}, 'fib_hits': {},
        'projections': [], 'invalidation': None, 'confidence': 0.0,
        'bias': 'neutral', 'phase': '', 'summary_es': reason,
    }


def analyze_elliott(df, depth=5, min_move_pct=0.5):
    """Analiza el DataFrame OHLC y devuelve el dict completo del análisis.

    Parámetros:
    - df: DataFrame con columnas timestamp, high, low, close (open/volume opcionales).
    - depth: sensibilidad del zigzag (barras a cada lado de un pivote).
    - min_move_pct: movimiento mínimo entre pivotes (%) para filtrar ruido.

    Retorna dict con: structure, waves, zigzag, rules, fibs, fib_hits,
    projections, invalidation, confidence, bias, phase, summary_es.
    """
    required = {'timestamp', 'high', 'low', 'close'}
    if df is None or df.empty or not required.issubset(df.columns):
        return _empty_result('Datos OHLC insuficientes para el análisis.')

    df = df.reset_index(drop=True)
    if len(df) < depth * 4 + 10:
        return _empty_result(f'Se necesitan más velas (mínimo {depth * 4 + 10}) para el zigzag.')

    pivots = _zigzag(df, depth=depth, min_move_pct=min_move_pct)
    if len(pivots) < 6:
        return _empty_result('No se detectaron suficientes pivotes en los datos.')

    # ── Mejor candidato a impulso (5 ondas) ──
    best_impulse = None
    for direction in (+1, -1):
        start_type = 'low' if direction > 0 else 'high'
        for s in range(len(pivots) - 5):
            seq = pivots[s:s + 6]
            if seq[0]['type'] != start_type:
                continue
            if any(seq[i]['type'] == seq[i + 1]['type'] for i in range(5)):
                continue
            ev = _evaluate_impulse(seq, direction)
            if ev and (best_impulse is None or ev['score'] > best_impulse['score']):
                best_impulse = {**ev, 'seq': seq, 'start': s, 'direction': direction}

    # ── Mejor candidato a corrección (A-B-C) ──
    best_correction = None
    for direction in (+1, -1):
        start_type = 'high' if direction > 0 else 'low'
        for s in range(len(pivots) - 3):
            seq = pivots[s:s + 4]
            if seq[0]['type'] != start_type:
                continue
            if any(seq[i]['type'] == seq[i + 1]['type'] for i in range(3)):
                continue
            ev = _evaluate_correction(seq, direction)
            if ev and (best_correction is None or ev['score'] > best_correction['score']):
                best_correction = {**ev, 'seq': seq, 'start': s, 'direction': direction}

    if best_impulse and best_impulse['score'] >= MIN_SCORE_IMPULSE:
        return _build_impulse_result(best_impulse, pivots, df)
    if best_correction and best_correction['score'] >= MIN_SCORE_CORRECTION:
        return _build_correction_result(best_correction, pivots, df)

    # Sin estructura clara: exponer el zigzag con etiquetas genéricas P1..Pn
    zigzag = _serialize_pivots(pivots[-8:])
    return {
        'status': 'ok',
        'error': None,
        'structure': 'indeterminate',
        'waves': [], 'zigzag': zigzag,
        'rules': {}, 'fibs': {}, 'fib_hits': {},
        'projections': [], 'invalidation': None, 'confidence': 0.0,
        'bias': 'neutral', 'phase': 'Sin patrón claro',
        'summary_es': ('No se encontró un impulso (1-2-3-4-5) ni una corrección '
                       '(A-B-C) que cumpla las reglas con confianza suficiente. '
                       'Se muestra el zigzag de pivotes para lectura manual.'),
    }


def _serialize_pivots(pivots):
    return [{'label': f'P{i + 1}', 'type': p['type'],
             'price': round(p['price'], 8), 'timestamp': pd.Timestamp(p['ts']),
             'idx': p['idx']}
            for i, p in enumerate(pivots)]


def _build_impulse_result(best, pivots, df):
    seq = best['seq']
    direction = best['direction']
    p = [s['price'] for s in seq]
    nd = 8
    labels = ['0', 'W1', 'W2', 'W3', 'W4', 'W5']
    waves = []
    for i, s in enumerate(seq):
        prev_price = p[i - 1] if i > 0 else None
        move_pct = None
        if prev_price and prev_price > 0:
            move_pct = round((p[i] - prev_price) / prev_price * 100, 2)
        waves.append({
            'label': labels[i], 'type': s['type'],
            'price': round(s['price'], nd), 'timestamp': pd.Timestamp(s['ts']),
            'idx': s['idx'], 'move_pct': move_pct,
        })

    if direction > 0:
        targets = [
            {'label': 'T1 · 0.618 × W1', 'price': round(p[4] + best['w1'] * 0.618, nd)},
            {'label': 'T2 · 1.0 × W1',   'price': round(p[4] + best['w1'] * 1.0, nd)},
            {'label': 'T3 · 1.618 × W1', 'price': round(p[4] + best['w1'] * 1.618, nd)},
            {'label': 'T4 · 0.618 × W3', 'price': round(p[4] + best['w3'] * 0.618, nd)},
        ]
        invalidation = round(p[0], nd)
        invalidation_label = 'Inicio de la onda 1'
        bias = 'bullish'
        bias_label = 'Alcista'
    else:
        targets = [
            {'label': 'T1 · 0.618 × W1', 'price': round(p[4] - best['w1'] * 0.618, nd)},
            {'label': 'T2 · 1.0 × W1',   'price': round(p[4] - best['w1'] * 1.0, nd)},
            {'label': 'T3 · 1.618 × W1', 'price': round(p[4] - best['w1'] * 1.618, nd)},
            {'label': 'T4 · 0.618 × W3', 'price': round(p[4] - best['w3'] * 0.618, nd)},
        ]
        invalidation = round(p[0], nd)
        invalidation_label = 'Inicio de la onda 1'
        bias = 'bearish'
        bias_label = 'Bajista'

    # Fase actual según el último pivote etiquetado
    last_label = labels[-1]  # W5 es el pivote final de la secuencia
    if last_label == 'W3':
        phase = 'Onda 4 en desarrollo'
    elif last_label == 'W4':
        phase = 'Onda 5 en desarrollo — rumbo a los objetivos'
    else:
        phase = 'Impulso completo — posible corrección A-B-C'

    close_now = float(df['close'].iloc[-1])
    if direction > 0 and close_now < p[0]:
        phase += ' (¡invalidado: precio bajo el inicio de la onda 1!)'
    elif direction < 0 and close_now > p[0]:
        phase += ' (¡invalidado: precio sobre el inicio de la onda 1!)'

    summary_es = (
        f"Impulso {'alcista' if direction > 0 else 'bajista'} de 5 ondas detectado "
        f"con confianza {best['score']:.0f}/100. {phase}. "
        f"Objetivos de la onda 5 entre ${targets[0]['price']:,.4g} y ${targets[-1]['price']:,.4g}. "
        f"Invalidación del conteo por debajo de ${invalidation:,.4g}."
    )

    return {
        'status': 'ok', 'error': None,
        'structure': 'impulse',
        'waves': waves,
        'zigzag': _serialize_pivots(pivots[-10:]),
        'rules': best['rules'], 'fibs': best['fibs'], 'fib_hits': best['fib_hits'],
        'projections': targets,
        'invalidation': {'price': invalidation, 'label': invalidation_label},
        'confidence': best['score'],
        'bias': bias, 'bias_label': bias_label,
        'phase': phase,
        'summary_es': summary_es,
        'direction': direction,
    }


def _build_correction_result(best, pivots, df):
    seq = best['seq']
    direction = best['direction']
    p = [s['price'] for s in seq]
    nd = 8
    labels = ['0', 'A', 'B', 'C']
    waves = []
    for i, s in enumerate(seq):
        prev_price = p[i - 1] if i > 0 else None
        move_pct = None
        if prev_price and prev_price > 0:
            move_pct = round((p[i] - prev_price) / prev_price * 100, 2)
        waves.append({
            'label': labels[i], 'type': s['type'],
            'price': round(s['price'], nd), 'timestamp': pd.Timestamp(s['ts']),
            'idx': s['idx'], 'move_pct': move_pct,
        })

    if direction > 0:  # corrección bajista tras impulso alcista
        targets = [
            {'label': 'C1 · 0.618 × A', 'price': round(p[2] - best['a'] * 0.618, nd)},
            {'label': 'C2 · 1.0 × A',   'price': round(p[2] - best['a'] * 1.0, nd)},
            {'label': 'C3 · 1.618 × A', 'price': round(p[2] - best['a'] * 1.618, nd)},
        ]
        invalidation = round(p[0], nd)
        invalidation_label = 'Fin de la onda 5 (origen de la corrección)'
        bias = 'bearish'
        bias_label = 'Correctiva bajista'
    else:
        targets = [
            {'label': 'C1 · 0.618 × A', 'price': round(p[2] + best['a'] * 0.618, nd)},
            {'label': 'C2 · 1.0 × A',   'price': round(p[2] + best['a'] * 1.0, nd)},
            {'label': 'C3 · 1.618 × A', 'price': round(p[2] + best['a'] * 1.618, nd)},
        ]
        invalidation = round(p[0], nd)
        invalidation_label = 'Fin de la onda 5 (origen de la corrección)'
        bias = 'bullish'
        bias_label = 'Correctiva alcista'

    last_label = labels[-1]
    if last_label == 'A':
        phase = 'Onda B en desarrollo'
    elif last_label == 'B':
        phase = 'Onda C en desarrollo — rumbo a los objetivos'
    else:
        phase = 'Corrección completa — posible nuevo impulso'

    close_now = float(df['close'].iloc[-1])
    if direction > 0 and close_now > p[0]:
        phase += ' (¡invalidado: precio sobre el origen de la corrección!)'
    elif direction < 0 and close_now < p[0]:
        phase += ' (¡invalidado: precio bajo el origen de la corrección!)'

    summary_es = (
        f"Corrección A-B-C {'bajista' if direction > 0 else 'alcista'} detectada "
        f"con confianza {best['score']:.0f}/100. {phase}. "
        f"Objetivos de la onda C entre ${targets[0]['price']:,.4g} y ${targets[-1]['price']:,.4g}. "
        f"Invalidación más allá de ${invalidation:,.4g}."
    )

    return {
        'status': 'ok', 'error': None,
        'structure': 'correction',
        'waves': waves,
        'zigzag': _serialize_pivots(pivots[-10:]),
        'rules': best['rules'], 'fibs': best['fibs'], 'fib_hits': best['fib_hits'],
        'projections': targets,
        'invalidation': {'price': invalidation, 'label': invalidation_label},
        'confidence': best['score'],
        'bias': bias, 'bias_label': bias_label,
        'phase': phase,
        'summary_es': summary_es,
        'direction': direction,
    }


# ── Interfaz compatible con el overlay anterior ─────────────────────────

def detect_waves(df, order=5):
    """Interfaz legacy para overlays de gráfico: lista de dicts
    {timestamp, price, label, type} etiquetados W1..W5 / A-B-C."""
    analysis = analyze_elliott(df, depth=order)
    waves = []
    for w in analysis.get('waves', []):
        waves.append({
            'timestamp': w['timestamp'],
            'price': w['price'],
            'label': w['label'],
            'type': w['type'],
        })
    return waves


# ── Gráfico ──────────────────────────────────────────────────────────────

def build_elliott_chart(df, analysis):
    """Construye el gráfico de velas con zigzag, ondas etiquetadas, objetivos
    e invalidación. Devuelve HTML (sin plotly.js, lo incluye el template)."""
    fig = go.Figure()

    fig.add_trace(go.Candlestick(
        x=df['timestamp'], open=df['open'], high=df['high'],
        low=df['low'], close=df['close'], name='Precio',
        increasing_line_color='#00e676', decreasing_line_color='#ff1744',
    ))

    # Zigzag de pivotes
    zigzag = analysis.get('zigzag', [])
    if zigzag:
        fig.add_trace(go.Scatter(
            x=[z['timestamp'] for z in zigzag], y=[z['price'] for z in zigzag],
            mode='lines', line=dict(color='rgba(139,148,158,0.55)', width=1.2),
            name='Zigzag', hoverinfo='skip',
        ))

    # Ondas etiquetadas
    waves = analysis.get('waves', [])
    if waves:
        wts = [w['timestamp'] for w in waves]
        wps = [w['price'] for w in waves]
        wls = [w['label'] for w in waves]
        fig.add_trace(go.Scatter(
            x=wts, y=wps, mode='lines+markers+text',
            line=dict(color='rgba(255,241,118,0.55)', width=1.6, dash='dashdot'),
            marker=dict(size=9, color=[WAVE_COLORS.get(l, '#ffffff') for l in wls],
                        line=dict(width=1, color='#000')),
            text=wls, textposition='top center',
            textfont=dict(size=12, color='#ffe082'),
            name='Ondas Elliott', hovertemplate='%{text}<br>%{y:,.6f}<extra></extra>',
        ))

    # Objetivos y niveles de invalidación (líneas horizontales al final del rango)
    proj = analysis.get('projections', [])
    inv = analysis.get('invalidation')
    if proj or inv:
        x0 = df['timestamp'].iloc[int(len(df) * 0.55)]
        x1 = df['timestamp'].iloc[-1]
        for t in proj:
            fig.add_shape(type='line', x0=x0, x1=x1, y0=t['price'], y1=t['price'],
                          line=dict(color='rgba(0,230,118,0.65)', width=1.2, dash='dot'))
            fig.add_annotation(x=x1, y=t['price'], text=f" {t['label']}",
                               showarrow=False, font=dict(color='#00e676', size=9),
                               xanchor='left', bgcolor='rgba(0,0,0,0.45)')
        if inv:
            fig.add_shape(type='line', x0=x0, x1=x1, y0=inv['price'], y1=inv['price'],
                          line=dict(color='rgba(255,23,68,0.75)', width=1.4, dash='dash'))
            fig.add_annotation(x=x1, y=inv['price'], text=' ✕ Invalidación',
                               showarrow=False, font=dict(color='#ff1744', size=10),
                               xanchor='left', bgcolor='rgba(0,0,0,0.45)')

    fig.update_layout(
        template='plotly_dark',
        paper_bgcolor='#1a1a2e',
        plot_bgcolor='#16213e',
        height=640,
        margin=dict(l=10, r=10, t=30, b=10),
        hovermode='x unified',
        legend=dict(orientation='h', yanchor='bottom', y=1.01, x=0),
        xaxis_rangeslider_visible=False,
    )
    return fig.to_html(full_html=False, include_plotlyjs=False)
