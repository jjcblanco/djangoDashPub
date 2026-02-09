"""
Vistas relacionadas con trading y ejecución de bots.

Este módulo contiene vistas para ejecutar análisis de trading y bots.
"""

from django.shortcuts import render
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.utils.safestring import mark_safe
from datetime import datetime, timedelta
from .. import ccxttest1
import pandas as pd


def ejecutar_analisis_trading(request):
    """Ejecuta el análisis completo y muestra resultados en el dashboard"""
    print("Ejecuta el análisis completo y muestra resultados en el dashboard")
    try:
        # Ejecutar el bot de trading
        resultados = run_bot()
        
        # Convertir a formato para el template
        señales = resultados[resultados['signal_buy_sell'].isin(['buy', 'sell'])]
        
        context = {
            'señales': señales.to_dict('records'),
            'ultima_actualizacion': pd.Timestamp.now(),
            'total_señales': len(señales),
            'señales_compra': len(señales[señales['signal_buy_sell'] == 'buy']),
            'señales_venta': len(señales[señales['signal_buy_sell'] == 'sell']),
        }
        
        return render(request, 'trading_bot/resultados.html', context)
    
    except Exception as e:
        return render(request, 'trading_bot/error.html', {'error': str(e)})


@require_http_methods(["GET", "POST"])
def run_bot_view(request):
    """Vista para ejecutar el bot de trading manualmente"""
    table_html = None
    if request.method == "POST":
        try:
            # Use a date in the past (30 days ago)
            date_from = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')
            # adjust function name if ccxttest1 uses a different name
            result = ccxttest1.run_bot('ETH/USDT', date_from, '1m')
            if hasattr(result, "to_html"):
                table_html = result.to_html(classes="table table-sm table-striped", index=False, border=0)
            else:
                df = pd.DataFrame(result)
                table_html = df.to_html(classes="table table-sm table-striped", index=False, border=0)
            messages.success(request, "Bot ejecutado correctamente")
        except Exception as e:
            messages.error(request, f"Error al ejecutar bot: {e}")
    return render(request, "dashboard/bot_run.html", {"table_html": mark_safe(table_html) if table_html else None})
