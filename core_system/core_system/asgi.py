import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
BASE_DIR_STRING = str(BASE_DIR)
if BASE_DIR_STRING not in sys.path:
    sys.path.insert(0, BASE_DIR_STRING)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core_system.settings")

from django.core.asgi import get_asgi_application

django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from apps.weighscale.routing import websocket_urlpatterns

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AuthMiddlewareStack(URLRouter(websocket_urlpatterns)),
    }
)
