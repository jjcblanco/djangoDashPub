from django.urls import path
from . import views
from . import auth_views

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
    path('api/run-bot/', views.run_bot_api, name='run_bot_api'),
    path('backtest/', views.backtest_view, name='backtest'),
]
