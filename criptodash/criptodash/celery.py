import os
from celery import Celery

# Establecer el módulo de settings por defecto de Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')

app = Celery('criptodash')

# Usar los settings de Django para la configuración de Celery
# namespace='CELERY' significa que todas las llaves de configuración de Celery
# deben tener el prefijo `CELERY_` (ej. CELERY_BROKER_URL)
app.config_from_object('django.conf:settings', namespace='CELERY')

# Descubrir y cargar automáticamente las tareas (tasks.py) de todas las apps instaladas
app.autodiscover_tasks()

@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
