import os
import django
from django.test import RequestFactory
from django.contrib.auth.models import User
from django.contrib.messages.storage.fallback import FallbackStorage

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')
django.setup()

from dashboard.views.bot_views import whale_insights

def simulate_request():
    factory = RequestFactory()
    request = factory.get('/whale-insights/')
    
    # Simular usuario autenticado
    user = User.objects.first()
    if not user:
        user = User.objects.create_user(username='testuser', password='password')
    request.user = user
    
    # Añadir soporte de mensajes
    setattr(request, '_messages', FallbackStorage(request))
    
    print("--- Simulando GET /whale-insights/ ---")
    try:
        response = whale_insights(request)
        print(f"Status Code: {response.status_code}")
        if response.status_code == 500:
            print("Error detectado en la respuesta!")
            print(response.content.decode('utf-8'))
        else:
            print("La vista ha respondido exitosamente.")
    except Exception as e:
        print("Crash detectado fuera del try-except de la vista!")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    simulate_request()
