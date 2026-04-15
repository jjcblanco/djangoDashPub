from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/whale-metrics/$', consumers.WhaleMetricsConsumer.as_asgi()),
]