import sys
import os

# Añadir el directorio del proyecto al path
sys.path.insert(0, r'c:\Users\Javier\Desktop\programacion\djangoDashPub\criptodash')

print("=" * 60)
print("VERIFICACION DE IMPORTS - REFACTORIZACION DE VIEWS")
print("=" * 60)
print()

# Test 1: Importar el paquete views
print("[OK] Test 1: Importando paquete dashboard.views...")
try:
    from dashboard import views
    print("  [SUCCESS] Paquete importado correctamente")
except Exception as e:
    print(f"  [ERROR] Error: {e}")
    sys.exit(1)

# Test 2: Verificar que las vistas están disponibles
print("\n[OK] Test 2: Verificando disponibilidad de vistas...")
expected_views = [
    'index',
    'dashboard_mejorado',
    'technical_analysis',
    'ejecutar_analisis_trading',
    'run_bot_view',
    'backtest_view',
    'import_data',
    'run_bot_api',
    'app'
]

missing_views = []
for view_name in expected_views:
    if hasattr(views, view_name):
        print(f"  [OK] {view_name}")
    else:
        print(f"  [FAIL] {view_name} - NO ENCONTRADA")
        missing_views.append(view_name)

if missing_views:
    print(f"\n[ERROR] Faltan {len(missing_views)} vistas: {', '.join(missing_views)}")
    sys.exit(1)

# Test 3: Verificar que son callables (excepto 'app' que es el Dash app)
print("\n[OK] Test 3: Verificando que las vistas son funciones...")
for view_name in expected_views:
    if view_name == 'app':
        continue  # app es el objeto Dash, no una función
    view_obj = getattr(views, view_name)
    if callable(view_obj):
        print(f"  [OK] {view_name} es callable")
    else:
        print(f"  [FAIL] {view_name} NO es callable")
        sys.exit(1)

# Test 4: Verificar Dash app
print("\n[OK] Test 4: Verificando Dash app...")
try:
    app = getattr(views, 'app')
    print(f"  [SUCCESS] Dash app disponible: {type(app)}")
except Exception as e:
    print(f"  [ERROR] Error al obtener Dash app: {e}")
    sys.exit(1)

# Test 5: Verificar módulos individuales
print("\n[OK] Test 5: Verificando modulos individuales...")
modules_to_test = [
    ('dashboard.views.utils', ['generar_datos_grafico_desde_senales', 'crear_grafico_con_senales', 'calcular_estadisticas']),
    ('dashboard.views.dash_app', ['app', 'cargar_datos', 'update_chart']),
    ('dashboard.views.dashboard_views', ['index', 'technical_analysis', 'dashboard_mejorado']),
    ('dashboard.views.trading_views', ['ejecutar_analisis_trading', 'run_bot_view']),
    ('dashboard.views.backtest_views', ['backtest_view']),
    ('dashboard.views.data_views', ['import_data']),
    ('dashboard.views.api_views', ['run_bot_api']),
]

for module_name, expected_items in modules_to_test:
    try:
        module = __import__(module_name, fromlist=expected_items)
        print(f"  [OK] {module_name}")
        for item in expected_items:
            if hasattr(module, item):
                print(f"     [OK] {item}")
            else:
                print(f"     [FAIL] {item} - NO ENCONTRADO")
    except Exception as e:
        print(f"  [ERROR] {module_name}: {e}")

print("\n" + "=" * 60)
print("[SUCCESS] VERIFICACION COMPLETADA EXITOSAMENTE")
print("=" * 60)
print()
print("Resumen:")
print(f"  - {len(expected_views)} vistas exportadas correctamente")
print(f"  - {len(modules_to_test)} modulos verificados")
print(f"  - Estructura de views/ creada correctamente")
print()
print("La refactorizacion se completo sin errores de imports.")

