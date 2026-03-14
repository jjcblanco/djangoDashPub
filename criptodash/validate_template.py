import os
import django
from django.template import Template, Context, loader

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')
django.setup()

def validate_template(template_path):
    print(f"Validating template: {template_path}")
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Intentar cargar la plantilla
        t = Template(content)
        print("[OK] Plantilla parseada correctamente.")
        
        # Intentar renderizar con un contexto básico
        ctx = Context({
            'page_title': 'Test',
            'wallets': [],
            'insights': []
        })
        t.render(ctx)
        print("[OK] Plantilla renderizada correctamente con contexto vacío.")
        
    except Exception as e:
        print(f"[ERROR] Fallo en la plantilla: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    path = os.path.join('dashboard', 'templates', 'dashboard', 'whale_insights.html')
    validate_template(path)
