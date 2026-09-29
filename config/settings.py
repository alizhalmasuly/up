import os
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env.local")
load_dotenv(BASE_DIR / ".env")

IS_VERCEL = os.getenv("VERCEL", "").lower() == "1"
DEBUG = os.getenv("DEBUG", "False" if IS_VERCEL else "True").lower() == "true"

SECRET_KEY = (
    os.getenv("SECRET_KEY")
    or os.getenv("DJANGO_SECRET_KEY", "")
).strip()

if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "dev-only-change-this-secret-key"
    else:
        raise ImproperlyConfigured(
            "SECRET_KEY must be configured when DEBUG is False"
        )

if not DEBUG and SECRET_KEY.startswith("replace-this"):
    raise ImproperlyConfigured(
        "Replace the example SECRET_KEY before deploying"
    )

ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv(
        "ALLOWED_HOSTS",
        "localhost,127.0.0.1,testserver"
    ).split(",")
    if host.strip()
]

# Vercel's VERCEL_URL is the unique deployment URL, while visitors may use
# the stable project alias (for example, up-qxch.vercel.app).
VERCEL_PROJECT_URL = os.getenv("VERCEL_PROJECT_PRODUCTION_URL", "").strip()
if VERCEL_PROJECT_URL and VERCEL_PROJECT_URL not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(VERCEL_PROJECT_URL)

CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "CSRF_TRUSTED_ORIGINS",
        ""
    ).split(",")
    if origin.strip()
]

VERCEL_URL = os.getenv("VERCEL_URL", "").strip()

if VERCEL_URL:
    if VERCEL_URL not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(VERCEL_URL)

    vercel_origin = f"https://{VERCEL_URL}"

    if vercel_origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(vercel_origin)

if VERCEL_PROJECT_URL:
    project_origin = f"https://{VERCEL_PROJECT_URL}"
    if project_origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(project_origin)


INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    "storages",

    "accounts",
    "mountains",
    "community",
    "weather",
    "ai_assistant",
    "core",
]


MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "core.middleware.RussianDefaultLocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.interface_text",
            ],
        },
    },
]


WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"


# Database

DATABASE_URL = (
    os.getenv("DATABASE_URL")
    or os.getenv("POSTGRES_URL")
)

if IS_VERCEL and not DATABASE_URL:
    raise ImproperlyConfigured(
        "Vercel requires a persistent PostgreSQL database. "
        "Set DATABASE_URL (or POSTGRES_URL) in the Vercel project environment."
    )

if DATABASE_URL:
    DATABASES = {
        "default": dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=0,
            conn_health_checks=True,
            ssl_require=not DEBUG,
        )
    }

elif DEBUG:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

else:
    raise ImproperlyConfigured(
        "Set DATABASE_URL or POSTGRES_URL to a persistent PostgreSQL database when DEBUG is False"
    )


# Redis

REDIS_URL = os.getenv("REDIS_URL", "").strip()

if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_URL,
        }
    }


AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME":
        "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {
        "NAME":
        "django.contrib.auth.password_validation.MinimumLengthValidator"
    },
    {
        "NAME":
        "django.contrib.auth.password_validation.CommonPasswordValidator"
    },
    {
        "NAME":
        "django.contrib.auth.password_validation.NumericPasswordValidator"
    },
]


# Language

LANGUAGE_CODE = "ru"

LANGUAGES = [
    ("ru", "Русский"),
    ("kk", "Қазақша"),
    ("en", "English"),
]

LOCALE_PATHS = [
    BASE_DIR / "locale"
]

TIME_ZONE = "Asia/Almaty"

USE_I18N = True
USE_TZ = True


# Static files

STATIC_URL = "static/"

STATICFILES_DIRS = [
    BASE_DIR / "static"
]

STATIC_ROOT = BASE_DIR / "staticfiles"

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage"
    },
    "staticfiles": {
        "BACKEND":
        "whitenoise.storage.CompressedManifestStaticFilesStorage"
    },
}

WHITENOISE_MANIFEST_STRICT = not DEBUG


# Media

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"


# AWS / S3

AWS_STORAGE_BUCKET_NAME = os.getenv(
    "AWS_STORAGE_BUCKET_NAME",
    ""
).strip()

if AWS_STORAGE_BUCKET_NAME:

    storage_options = {
        "bucket_name": AWS_STORAGE_BUCKET_NAME,
        "region_name": os.getenv(
            "AWS_S3_REGION_NAME"
        ) or None,
        "endpoint_url": os.getenv(
            "AWS_S3_ENDPOINT_URL"
        ) or None,
        "custom_domain": os.getenv(
            "AWS_S3_CUSTOM_DOMAIN"
        ) or None,
        "access_key": os.getenv(
            "AWS_ACCESS_KEY_ID"
        ) or None,
        "secret_key": os.getenv(
            "AWS_SECRET_ACCESS_KEY"
        ) or None,
        "file_overwrite": False,
        "default_acl": None,
    }

    STORAGES["default"] = {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": storage_options,
    }


# Mountain search

MOUNTAIN_SEARCH_URL = os.getenv(
    "MOUNTAIN_SEARCH_URL",
    "https://nominatim.openstreetmap.org/search"
)

MOUNTAIN_SEARCH_USER_AGENT = os.getenv(
    "MOUNTAIN_SEARCH_USER_AGENT",
    "tau-hiking-platform/1.0"
)

MOUNTAIN_SEARCH_CONTACT = os.getenv(
    "MOUNTAIN_SEARCH_CONTACT",
    ""
)

OVERPASS_API_URL = os.getenv(
    "OVERPASS_API_URL",
    "https://overpass-api.de/api/interpreter"
)

MAP_TILE_URL = os.getenv(
    "MAP_TILE_URL",
    "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
)

MAP_TILE_ATTRIBUTION = os.getenv(
    "MAP_TILE_ATTRIBUTION",
    "© OpenStreetMap contributors"
)


# Weather

WEATHER_API_URL = os.getenv(
    "WEATHER_API_URL",
    "https://api.openweathermap.org/data/2.5/weather"
)

WEATHER_FORECAST_API_URL = os.getenv(
    "WEATHER_FORECAST_API_URL",
    "https://api.openweathermap.org/data/2.5/forecast"
)


# Security

SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG

SECURE_SSL_REDIRECT = os.getenv(
    "SECURE_SSL_REDIRECT",
    str(not DEBUG)
).lower() == "true"

SECURE_HSTS_SECONDS = int(
    os.getenv(
        "SECURE_HSTS_SECONDS",
        "31536000" if not DEBUG else "0"
    )
)

SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG

SECURE_PROXY_SSL_HEADER = (
    "HTTP_X_FORWARDED_PROTO",
    "https"
)

SECURE_CONTENT_TYPE_NOSNIFF = True

SECURE_REFERRER_POLICY = (
    "strict-origin-when-cross-origin"
)


# Authentication

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "accounts:profile"
LOGOUT_REDIRECT_URL = "core:home"


DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
