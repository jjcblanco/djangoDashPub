"""
Dashboard views package.

Este paquete contiene todas las vistas del dashboard organizadas por responsabilidad.
Los imports están expuestos aquí para mantener compatibilidad con el código existente.
"""

# Importar vistas de dashboard
from .dashboard_views import (
    index,
    technical_analysis,
    dashboard_mejorado
)

# Importar vistas de trading
from .trading_views import (
    ejecutar_analisis_trading,
    run_bot_view
)

# Importar vistas de backtest
from .backtest_views import backtest_view

# Importar vistas de datos
from .data_views import import_data

# Importar API views
from .api_views import run_bot_api

# Importar Dash app
from .dash_app import app

# Exportar todas las vistas para compatibilidad con urls.py
__all__ = [
    # Dashboard views
    'index',
    'technical_analysis',
    'dashboard_mejorado',
    
    # Trading views
    'ejecutar_analisis_trading',
    'run_bot_view',
    
    # Backtest views
    'backtest_view',
    
    # Data views
    'import_data',
    
    # API views
    'run_bot_api',
    
    # Dash app
    'app',
]
