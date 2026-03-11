import os
import sys
import django
from django.template import Template, Context

# Añadir el directorio del proyecto al path
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')

try:
    django.setup()
    
    # Intentar cargar el contenido de la plantilla
    path = 'dashboard/templates/dashboard/bot_dashboard.html'
    if not os.path.exists(path):
         # Probar path relativo desde la raíz del repo si falla
         path = 'criptodash/dashboard/templates/dashboard/bot_dashboard.html'

    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Intentar parsear la plantilla
    Template(content)
    print("SUCCESS: La plantilla se parseó correctamente.")
    
except Exception as e:
    print(f"ERROR DE PLANTILLA: {e}")
    import traceback
    traceback.print_exc()
