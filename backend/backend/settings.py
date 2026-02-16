import os
import json
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

try:
    import dj_database_url
except ImportError:  # pragma: no cover
    dj_database_url = None

try:
    import corsheaders  # noqa: F401
    HAS_CORSHEADERS = True
except ImportError:  # pragma: no cover
    HAS_CORSHEADERS = False

load_dotenv()
BASE_DIR = Path(__file__).resolve().parent.parent


def _parse_allowed_hosts(raw_value: str | None):
    if not raw_value:
        return ["*"]

    value = raw_value.strip()
    if not value:
        return ["*"]

    # Accept JSON array or comma-separated string.
    if value.startswith("["):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                tokens = [str(item).strip() for item in parsed if str(item).strip()]
            else:
                tokens = [value]
        except json.JSONDecodeError:
            tokens = [segment.strip() for segment in value.strip("[]").split(",") if segment.strip()]
    else:
        tokens = [segment.strip() for segment in value.split(",") if segment.strip()]

    hosts = []
    for token in tokens:
        cleaned = token.strip().strip('"').strip("'").strip()
        if not cleaned:
            continue
        if cleaned == "*":
            return ["*"]

        # If scheme is present, extract hostname.
        if "://" in cleaned:
            parsed = urlparse(cleaned)
            cleaned = parsed.hostname or ""

        # Strip any path/port residues if entered manually.
        cleaned = cleaned.split("/")[0].split(":")[0].strip()
        if cleaned:
            hosts.append(cleaned)

    return hosts or ["*"]


def _with_render_hostname(hosts: list[str]):
    render_hostname = (os.getenv("RENDER_EXTERNAL_HOSTNAME") or "").strip()
    if not render_hostname:
        return hosts

    normalized = [host for host in hosts if host]
    if render_hostname not in normalized:
        normalized.append(render_hostname)
    return normalized


SECRET_KEY = os.getenv("DJANGO_SECRET_KEY")
DEBUG = os.getenv("DEBUG", "False").lower() == "true"
ALLOWED_HOSTS = _with_render_hostname(_parse_allowed_hosts(os.getenv("ALLOWED_HOSTS", "*")))

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

CORS_ALLOW_ALL_ORIGINS = os.getenv("CORS_ALLOW_ALL_ORIGINS", "True").lower() == "true"


def _parse_cors_origins(raw_value: str | None):
    if not raw_value:
        return []

    value = raw_value.strip()
    if not value:
        return []

    # Accept either JSON array or comma-separated string.
    if value.startswith("["):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return [str(origin).strip().strip('"').strip("'").rstrip("/") for origin in parsed if str(origin).strip()]
        except json.JSONDecodeError:
            pass

    # Handle loose bracketed strings like:
    # [https://a.vercel.app,https://b.vercel.app/]
    value = value.strip().lstrip("[").rstrip("]")

    cleaned_origins = []
    for segment in value.split(","):
        origin = segment.strip().strip('"').strip("'").strip().lstrip("[").rstrip("]").rstrip("/")
        if not origin:
            continue
        cleaned_origins.append(origin)
    return cleaned_origins


CORS_ALLOWED_ORIGINS = _parse_cors_origins(
    os.getenv(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    )
)

