import os
import sys
from pathlib import Path

from django.core.wsgi import get_wsgi_application


BASE_DIR = Path(__file__).resolve().parent.parent
BASE_DIR_STRING = str(BASE_DIR)
if BASE_DIR_STRING not in sys.path:
    sys.path.insert(0, BASE_DIR_STRING)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core_system.settings")

application = get_wsgi_application()

