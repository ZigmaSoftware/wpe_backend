from __future__ import annotations

import os
import sys
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BASE_DIR.parent
GRN_SERVICE_DIR = PROJECT_ROOT / "grn_service"

for project_path in (BASE_DIR, GRN_SERVICE_DIR):
    project_path_string = str(project_path)
    if project_path_string not in sys.path:
        sys.path.insert(0, project_path_string)

load_dotenv(PROJECT_ROOT / ".env")


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: list[str] | None = None) -> list[str]:
    value = os.getenv(name)
    if not value:
        return list(default or [])
    return [item.strip() for item in value.split(",") if item.strip()]


SECRET_KEY = os.getenv("SECRET_KEY", "django-insecure-change-me")
DEBUG = env_bool("DEBUG", True)

ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", ["127.0.0.1", "localhost"])
CORS_ALLOWED_ORIGINS = env_list(
    "CORS_ALLOWED_ORIGINS",
    [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
    ],
)
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", CORS_ALLOWED_ORIGINS)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "rest_framework_simplejwt.token_blacklist",
    "django_filters",
    "apps.login_home.apps.LoginHomeConfig",
    "apps.common_master.apps.CommonMasterConfig",
    "apps.admin_master.apps.AdminMasterConfig",
    "apps.auth",
    "apps.contacts",
    "apps.items",
    "apps.store",
    "apps.blending",
    "apps.production.apps.ProductionConfig",
    "apps.wpe_masters.apps.WpeMastersConfig",
    "apps.scale.apps.ScaleConfig",
    "apps.inventory.apps.InventoryConfig",
    "grn_app.apps.PurchasesIwardsConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "common.middleware.DisableAPICSRFMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "common.middleware.APIAuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "core_system.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "core_system.wsgi.application"
ASGI_APPLICATION = "core_system.asgi.application"

DATABASES = {   
    'default': {
        'ENGINE': os.getenv("DB_ENGINE", "django.db.backends.mysql"),
        'NAME': os.getenv("DB_NAME", "wpe_db"), 
        'USER': os.getenv("DB_USER", "root"),
        'PASSWORD': os.getenv("DB_PASSWORD", "admin@123"),
        'HOST': os.getenv("DB_HOST", "127.0.0.1"),
        'PORT': os.getenv("DB_PORT", "3306"),
        'OPTIONS': {
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
        },
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = os.getenv("DJANGO_TIME_ZONE", "Asia/Kolkata")
PRODUCTION_SCANCODE_TIME_ZONE = os.getenv("PRODUCTION_SCANCODE_TIME_ZONE", "Asia/Kolkata")
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]

API_PATH_PREFIX = "/api/"
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY", "").strip()

default_api_auth_exempt_paths = [
    "/api/token/",
    "/api/token/refresh/",
    "/api/token/verify/",
    "/api/auth/login/",
]
API_AUTH_EXEMPT_PATHS = list(
    dict.fromkeys(default_api_auth_exempt_paths + env_list("API_AUTH_EXEMPT_PATHS"))
)

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "common.authentication.APIKeyAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=int(os.getenv("JWT_ACCESS_MINUTES", "30"))),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=int(os.getenv("JWT_REFRESH_DAYS", "7"))),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

GRN_SERVICE_BASE_URL = os.getenv("GRN_SERVICE_BASE_URL", "").strip()
GRN_SERVICE_API_KEY = os.getenv("GRN_SERVICE_API_KEY", "").strip()

# Point Digi Scale serial connection
# Set SCALE_ENABLED=false to disable serial port probing and always return a disconnected payload.
# Set SERIAL_PORT=AUTO to auto-detect CH340 by VID/PID, or use explicit port e.g. /dev/ttyUSB0
SCALE_ENABLED    = env_bool("SCALE_ENABLED", True)
SERIAL_PORT      = os.getenv("SERIAL_PORT", "AUTO")
SERIAL_BAUD_RATE = int(os.getenv("SERIAL_BAUD_RATE", "9600"))
