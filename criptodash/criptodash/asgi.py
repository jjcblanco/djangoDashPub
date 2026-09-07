"""
ASGI config for criptodash project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'criptodash.settings')

# Initialize Django FIRST before importing routing/consumers (which touch models)
from django.core.asgi import get_asgi_application
django_asgi_app = get_asgi_application()

# Now it's safe to import Channels routing (which imports models via consumers)
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
import dashboard.routing

application = ProtocolTypeRouter({
    'http': django_asgi_app,
    'websocket': AuthMiddlewareStack(
        URLRouter(
            dashboard.routing.websocket_urlpatterns
        )
    ),
})
