import os
import sys
from pathlib import Path

from django.core.wsgi import get_wsgi_application


BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BASE_DIR.parent
CORE_SYSTEM_DIR = PROJECT_ROOT / "core_system"

for path in (BASE_DIR, CORE_SYSTEM_DIR):
    path_string = str(path)
    if path_string not in sys.path:
        sys.path.insert(0, path_string)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "grn_service.settings")

application = get_wsgi_application()

