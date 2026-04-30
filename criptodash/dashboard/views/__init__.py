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
    apply_strategic_optimizations,
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
    trigger_whale_hunt,
    hunt_targets_list,
    hunt_targets_add,
    hunt_targets_toggle,
    hunt_targets_delete,
    whale_consensus_ajax,
    whale_live_metrics,
    whale_trade_chart_ajax,
    learn_patterns,
    bulk_import_whales,
    trigger_retroactive_enrichment,
    trigger_extended_pattern_learning,
    whale_token_stats_ajax,
    whale_behavior_ajax,
)

# Importar vistas de simulaciones / shadow trading (NUEVO)
from .shadow_views import (
    simulate_whale_trade,
    close_shadow_trade,
    whale_live_prices,
)

# Importar vistas de scalping
from .scalping_views import (
    scalping_dashboard,
    scalping_api_alerts,
    scalping_api_scan_results,
    scalping_api_bot_stats,
    scalping_create_bot,
    scalping_bot_action,
    scalping_dismiss_alert,
    scalping_trigger_scan,
    scalping_close_trade,
    toggle_autopilot,
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
    'apply_strategic_optimizations',
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
    'trigger_whale_hunt',
    'hunt_targets_list',
    'hunt_targets_add',
    'hunt_targets_toggle',
    'hunt_targets_delete',
    'learn_patterns',
    'trigger_extended_pattern_learning',
    'bulk_import_whales',
    'trigger_retroactive_enrichment',
    'simulate_whale_trade',
    'close_shadow_trade',
    'whale_token_stats_ajax',
    'whale_behavior_ajax',

    # Scalping views
    'scalping_dashboard',
    'scalping_api_alerts',
    'scalping_api_scan_results',
    'scalping_api_bot_stats',
    'scalping_create_bot',
    'scalping_bot_action',
    'scalping_dismiss_alert',
    'scalping_trigger_scan',
    'scalping_close_trade',

    # Dash app
    'app',
]
