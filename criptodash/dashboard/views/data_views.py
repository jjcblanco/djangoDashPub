"""
Vistas de importación y gestión de datos.

Este módulo contiene vistas para importar datos desde exchanges externos.
"""

from django.shortcuts import render
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.utils.safestring import mark_safe
from .. import ccxttest1
import pandas as pd


@require_http_methods(["GET", "POST"])
def import_data(request):
    """Vista para importar datos desde exchanges"""
    table_html = None
    if request.method == "POST":
        try:
            result = ccxttest1.run_bot('ETH/USDT', '2025-11-16 18:15:00', '1m')
            print(result)
            if hasattr(result, "to_html"):
                table_html = result.to_html(classes="table table-sm table-striped", index=False, border=0)
            else:
                print("entro aca")
                df = pd.DataFrame(result)
                table_html = df.to_html(classes="table table-sm table-striped", index=False, border=0)

            messages.success(request, "Datos importados correctamente")
        except Exception as e:
            messages.error(request, f"Error al importar datos: {e}")
    return render(request, "dashboard/bot_run.html", {"table_html": mark_safe(table_html) if table_html else None})
