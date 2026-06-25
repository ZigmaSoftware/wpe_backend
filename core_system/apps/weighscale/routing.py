from django.urls import path
from .consumers import WeighscaleConsumer

websocket_urlpatterns = [
    path("ws/weighscale/", WeighscaleConsumer.as_asgi()),
]
