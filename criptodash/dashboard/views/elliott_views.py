"""
Vista del Analizador de Ondas de Elliott.

Página dedicada que analiza un par con detalle: zigzag de pivotes, detección
de impulsos (1-2-3-4-5) y correcciones (A-B-C), reglas clásicas, relaciones
de Fibonacci, proyecciones, invalidación y score de confianza.
"""

import logging

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from ..data_service import DataManager
from ..elliott import analyze_elliott, build_elliott_chart

logger = logging.getLogger(__name__)

PAIRS = [
    'BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT',
    'ADA/USDT', 'DOGE/USDT', 'LINK/USDT', 'AVAX/USDT', 'MATIC/USDT',
    'LTC/USDT', 'ATOM/USDT', 'NEAR/USDT', 'ARB/USDT', 'OP/USDT',
]
TIMEFRAMES = ['15m', '30m', '1h', '4h', '1d']


def _serialize(analysis):
    """Convierte el análisis a un dict JSON-safe para el template."""
    import copy
    out = copy.deepcopy(analysis)
    for w in out.get('waves', []):
        w['timestamp_str'] = w['timestamp'].strftime('%d/%m/%y %H:%M')
        w.pop('timestamp', None)
    for z in out.get('zigzag', []):
        z.pop('timestamp', None)
    return out


@login_required
def elliott_analysis(request):
    """Analizador de ondas de Elliott para un par y timeframe."""
    pair = request.GET.get('pair', 'BTC/USDT').upper().strip()
    timeframe = request.GET.get('timeframe', '4h')
    if timeframe not in TIMEFRAMES:
        timeframe = '4h'
    try:
        limit = min(max(int(request.GET.get('limit', 500)), 200), 1000)
    except (TypeError, ValueError):
        limit = 500

    error_message = None
    chart_html = None
    analysis = None

    try:
        df = DataManager.get_or_fetch(pair, timeframe=timeframe, limit=limit)
        if df is None or df.empty:
            error_message = f'No se pudieron obtener datos de {pair} en {timeframe}. Verificá el par o intentá de nuevo.'
        else:
            analysis = analyze_elliott(df)
            if analysis.get('status') == 'error':
                error_message = analysis.get('error', 'Datos insuficientes para el análisis.')
            else:
                chart_html = build_elliott_chart(df, analysis)
                analysis = _serialize(analysis)
    except Exception as e:
        logger.exception('Error en elliott_analysis para %s %s', pair, timeframe)
        error_message = f'Error al analizar {pair}: {e}'

    context = {
        'page_title': 'Elliott Wave Analyzer',
        'pair': pair,
        'timeframe': timeframe,
        'pairs': PAIRS,
        'timeframes': TIMEFRAMES,
        'analysis': analysis,
        'chart_html': chart_html,
        'error_message': error_message,
    }
    return render(request, 'dashboard/elliott.html', context)
