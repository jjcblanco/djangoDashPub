"""
API endpoints para el dashboard.

Este módulo contiene endpoints API que devuelven respuestas JSON,
utilizados principalmente por la aplicación Dash y llamadas AJAX.
"""

from django.http import JsonResponse
from .. import ccxttest1
import pandas as pd


def run_bot_api(request):
    """
    API endpoint para ejecutar el bot de trading.
    
    Parámetros GET:
        - pair: Par de trading (default: 'ETH/USDT')
        - date_from: Fecha de inicio (opcional)
        - timeframe: Intervalo de tiempo (default: '1m')
    
    Returns:
        JSON con los datos del bot o error
    """
    pair = request.GET.get('pair', 'ETH/USDT')
    date_from = request.GET.get('date_from')  # optional
    timeframe = request.GET.get('timeframe', '1m')

    try:
        # Intentar varias firmas comunes
        try:
            result = ccxttest1.run_bot(pair=pair, date_from=date_from, timeframe=timeframe)
        except TypeError:
            try:
                result = ccxttest1.run_bot(pair, date_from, timeframe)
            except Exception:
                result = ccxttest1.run_bot()

        # Normalizar salida a una lista de dicts
        if hasattr(result, "to_dict"):
            data = result.to_dict('records')
        elif isinstance(result, list):
            data = result
        else:
            try:
                df = pd.DataFrame(result)
                data = df.to_dict('records')
            except Exception:
                data = {'result': str(result)}

        safe_flag = isinstance(data, dict)
        return JsonResponse(data, safe=safe_flag)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
