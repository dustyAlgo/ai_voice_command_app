import os
import json
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlparse
import dj_database_url
import corsheaders

from dotenv import load_dotenv


load_dotenv()
BASE_DIR = Path(__file__).resolve().parent.parent


SECRET_KEY = os.getenv("DJANGO_SECRET_KEY")
DEBUG = os.getenv("DEBUG", "False").lower() == "true"


def _parse_env_list(raw_value):
    if not raw_value:
        return []
    value = raw_value.strip()
    if not value:
        return []
    if value.startswith("["):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
        except json.JSONDecodeError:
            pass
    return [item.strip() for item in value.split(",") if item.strip()]


def _normalize_allowed_host(host):
    candidate = host.strip()
    if not candidate:
        return ""
    if "://" in candidate:
        parsed = urlparse(candidate)
        candidate = parsed.netloc or parsed.path
    candidate = candidate.split("/")[0]
    if ":" in candidate and not candidate.startswith("["):
        candidate = candidate.split(":", 1)[0]
    return candidate


def _normalize_origin(origin):
    candidate = origin.strip().rstrip("/")
    if not candidate:
        return ""
    if "://" not in candidate:
        if candidate.startswith(("localhost", "127.0.0.1")):
            candidate = f"http://{candidate}"
        else:
            candidate = f"https://{candidate}"
    parsed = urlparse(candidate)
    if not parsed.scheme or not parsed.netloc:
        return ""
    return f"{parsed.scheme}://{parsed.netloc}"


default_allowed_hosts = [
    "ai-voice-command-app-1.onrender.com",
    "127.0.0.1",
    "localhost",
]
allowed_hosts_from_env = _parse_env_list(os.getenv("ALLOWED_HOSTS", ""))
ALLOWED_HOSTS = [
    _normalize_allowed_host(host)
    for host in (allowed_hosts_from_env or default_allowed_hosts)
]
ALLOWED_HOSTS = [host for host in ALLOWED_HOSTS if host]

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL")
GEMINI_FALLBACK_MODELS = os.getenv("GEMINI_FALLBACK_MODELS")

STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "accounts",
    "catalog",
    "shopping.apps.ShoppingConfig",
    "ai",
    "voice",
    "common",
    "corsheaders"
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


ROOT_URLCONF = "backend.urls"

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

WSGI_APPLICATION = "backend.wsgi.application"

DATABASES = {
    "default": dj_database_url.config(
        default="sqlite:///db.sqlite3"
    )
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "accounts.User"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=24),
    "AUTH_HEADER_TYPES": ("Bearer",),
}

default_cors_allowed_origins = [
    "https://ai-voice-command-app.vercel.app",
]
cors_origins_from_env = _parse_env_list(os.getenv("CORS_ALLOWED_ORIGINS", ""))
CORS_ALLOWED_ORIGINS = [
    _normalize_origin(origin)
    for origin in (cors_origins_from_env or default_cors_allowed_origins)
]
CORS_ALLOWED_ORIGINS = [origin for origin in CORS_ALLOWED_ORIGINS if origin]

