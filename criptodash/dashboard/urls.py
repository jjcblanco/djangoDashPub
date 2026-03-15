from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from . import views
from . import auth_views
from .views import api_views, bot_views # Para asegurar acceso a follow_whale si es necesario

router = DefaultRouter()
router.register(r'bots', api_views.LiveBotViewSet, basename='api_bots')
router.register(r'trades', api_views.LiveTradeViewSet, basename='api_trades')
router.register(r'trading-pairs', api_views.TradingPairViewSet, basename='api_trading_pairs')

urlpatterns = [
    path('', views.index, name='dashboard_index'),
    path('login/', auth_views.custom_login, name='custom_login'),
    path('register/', auth_views.custom_register, name='custom_register'),
    path('logout/', auth_views.custom_logout, name='custom_logout'),
    path('profile/', auth_views.profile, name='profile'),
    path('technical-analysis/', views.technical_analysis, name='technical_analysis'),
    path('run-bot/', views.run_bot_view, name='run_bot'),
    path('import-data/', views.import_data, name='import_data'),
    path('ejecutar-analisis/', views.ejecutar_analisis_trading, name='ejecutar_analisis'),
    path('nuevo/', views.dashboard_mejorado, name='dashboard_nuevo'),
    path('backtest/', views.backtest_view, name='backtest'),
    path('range-scanner/', views.range_scanner, name='range_scanner'),
    path('trend-scanner/', views.trend_scanner, name='trend_scanner'),
    
    # Bot Management URLs
    path('bots/', views.bot_dashboard, name='bot_dashboard'),
    path('bots/create/', views.create_bot, name='create_bot'),
    path('bots/edit/<int:bot_id>/', views.edit_bot, name='edit_bot'),
    path('bots/action/<int:bot_id>/', views.bot_action, name='bot_action'),
    path('bots/update/', views.trigger_bot_update, name='trigger_bot_update'),
    path('bots/sync-balance/', views.trigger_balance_sync, name='trigger_balance_sync'),
    path('bots/add-funding/', views.add_funding, name='add_funding'),
    path('api/volatility/', views.analyze_volatility_api, name='api_volatility'),
    path('whale-insights/', views.whale_insights, name='whale_insights'),
    path('whale-insights/follow/', views.follow_whale, name='follow_whale'),
    path('whale-insights/unfollow/<int:wallet_id>/', views.unfollow_whale, name='unfollow_whale'),
    path('whale-insights/simulate/', views.simulate_whale_trade, name='simulate_whale_trade'),
    path('whale-insights/shadow/close/<int:trade_id>/', views.close_shadow_trade, name='close_shadow_trade'),
    path('bots/<validation_id>/detail/', views.bot_detail, name='bot_detail'),
    path('bots/kill-switch/', views.trigger_kill_switch, name='trigger_kill_switch'),
    path('bots/risk-settings/', views.update_risk_settings, name='update_risk_settings'),
    path('bots/test-telegram/', views.test_telegram_view, name='test_telegram_view'),

    # REST API V1
    path('api/v1/', include(router.urls)),
    path('api/v1/token/', api_views.CustomObtainAuthToken.as_view(), name='api_token'),
]
