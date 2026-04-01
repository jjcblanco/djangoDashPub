"""
Dashboard views package.

Este paquete contiene todas las vistas del dashboard organizadas por responsabilidad.
Los imports están expuestos aquí para mantener compatibilidad con el código existente.
"""

# Importar vistas de dashboard
from .dashboard_views import (
    index,
    technical_analysis,
    dashboard_mejorado,
    range_scanner,
    trend_scanner
)

# Importar vistas de trading
from .trading_views import (
    ejecutar_analisis_trading,
    run_bot_view
)

# Importar vistas de backtest
from .backtest_views import backtest_view

# Importar vistas de bot finales
from .bot_views import (
    bot_dashboard,
    create_bot,
    bot_action,
    trigger_bot_update,
    trigger_balance_sync,
    add_funding,
    analyze_volatility_api,
    trigger_kill_switch,
    update_risk_settings,
    test_telegram_view,
    bot_detail,
    edit_bot,
)

# Importar vistas de ballenas (NUEVO)
from .whale_views import (
    whale_insights,
    follow_whale,
    unfollow_whale,
    search_tokens_ajax,
    get_whale_history,
    export_whale_history,
    trigger_deep_sync,
    get_whale_insights,
    whale_scores_ajax,
    whale_hot_tokens_ajax,
    suggest_bot_from_whale,
    discover_contract_whales_ajax,
)

# Importar vistas de simulaciones / shadow trading (NUEVO)
from .shadow_views import (
    simulate_whale_trade,
    close_shadow_trade,
    whale_live_prices,
)

# Importar vistas de datos
from .data_views import import_data

# Importar API views
from .api_views import (
    LiveBotViewSet,
    LiveTradeViewSet,
    TradingPairViewSet,
    CustomObtainAuthToken
)

# Importar Dash app
from .dash_app import app

# Exportar todas las vistas para compatibilidad con urls.py
__all__ = [
    'index',
    'technical_analysis',
    'dashboard_mejorado',
    'range_scanner',
    'trend_scanner',
    
    # Trading views
    'ejecutar_analisis_trading',
    'run_bot_view',
    
    # Backtest views
    'backtest_view',
    
    # Data views
    'import_data',
    
    # API views
    # API views
    'LiveBotViewSet',
    'LiveTradeViewSet',
    'TradingPairViewSet',
    'CustomObtainAuthToken',
    
    # Bot views
    'bot_dashboard',
    'create_bot',
    'bot_action',
    'trigger_bot_update',
    'trigger_balance_sync',
    'add_funding',
    'analyze_volatility_api',
    'trigger_kill_switch',
    'update_risk_settings',
    'test_telegram_view',
    'bot_detail',
    'edit_bot',
    'whale_insights',
    'follow_whale',
    'unfollow_whale',
    'simulate_whale_trade',
    'close_shadow_trade',
    'search_tokens_ajax',
    'get_whale_history',
    'export_whale_history',
    'trigger_deep_sync',
    'get_whale_insights',
    'whale_live_prices',
    'whale_scores_ajax',
    'whale_hot_tokens_ajax',
    'suggest_bot_from_whale',
    'discover_contract_whales_ajax',
    'simulate_whale_trade',
    'close_shadow_trade',

    # Dash app
    'app',
]
