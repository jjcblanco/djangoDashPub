import os
import sys

# 1. Cargar .env manualmente (como en el script de migración que funcionó)
def load_env_manually():
    try:
        env_path = '.env'
        if not os.path.exists(env_path):
            env_path = os.path.join('..', '.env')
        
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    if line.strip() and not line.startswith('#'):
                        if '=' in line:
                            key, value = line.strip().split('=', 1)
                            os.environ[key] = value.strip('"').strip("'")
            print(f"[OK] .env cargado.")
        else:
            print("[!] No se encontró .env")
    except Exception as e:
        print(f"[!] Error cargando .env: {e}")

load_env_manually()

# 2. Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')
try:
    import django
    django.setup()
    print("[OK] Django configurado.")
except Exception as e:
    print(f"[ERROR CRÍTICO] Django no arranca: {e}")
    sys.exit(1)

# 3. Probar la vista
from django.test import RequestFactory
from django.contrib.auth.models import User
from django.contrib.messages.storage.fallback import FallbackStorage
from dashboard.views.bot_views import whale_insights

def run_diagnosis():
    print("\n--- Iniciando Diagnóstico de Sincronización Whale Insights ---")
    factory = RequestFactory()
    request = factory.get('/whale-insights/?sync=1')
    
    # Usuario
    user = User.objects.first()
    if not user:
        print("[!] No hay usuarios en la DB. Creando uno temporal...")
        user = User.objects.create_user(username='diag_user', password='password')
    request.user = user
    
    # Mensajes y Sesión
    from django.contrib.sessions.middleware import SessionMiddleware
    middleware = SessionMiddleware(lambda r: None)
    middleware.process_request(request)
    request.session.save()
    setattr(request, '_messages', FallbackStorage(request))
    
    try:
        print("[...] Renderizando vista...")
        response = whale_insights(request)
        print(f"[OK] Status Code: {response.status_code}")
        
        if response.status_code == 500:
            print("\n[ERROR DETECTADO]")
            # Intentar extraer el traceback del HTML que devuelve nuestra vista
            content = response.content.decode('utf-8')
            if "<pre>" in content:
                trace = content.split("<pre>")[1].split("</pre>")[0]
                print(f"Traceback:\n{trace}")
            else:
                print(f"Contenido de error:\n{content[:500]}...")
        else:
            print("[EXITO] La vista funciona correctamente en este entorno.")
            
    except Exception:
        print("\n[CRASH FUERA DE LA VISTA]")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_diagnosis()
