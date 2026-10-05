"""Django settings for Hezarfen. All configuration comes from environment variables."""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-insecure-change-me")
DEBUG = os.environ.get("DJANGO_DEBUG", "0") == "1"
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,backend")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS", "http://localhost:8800")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "django.contrib.gis",
    "django.contrib.postgres",
    "channels",
    "rest_framework",
    "rest_framework_gis",
    "drf_spectacular",
    "ops",
    "tracking",
    "reference",
    "geofencing",
    "terrain",
    "realtime",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # serves /static/ from the app itself: uvicorn has no runserver-style static handling
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "hezarfen.urls"

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

WSGI_APPLICATION = "hezarfen.wsgi.application"
ASGI_APPLICATION = "hezarfen.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.contrib.gis.db.backends.postgis",
        "NAME": os.environ.get("POSTGRES_DB", "hezarfen"),
        "USER": os.environ.get("POSTGRES_USER", "hezarfen"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "hezarfen"),
        "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
        # keep connections open between requests instead of reconnecting each time
        "CONN_MAX_AGE": 60,
        "CONN_HEALTH_CHECKS": True,
    }
}

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

POSITIONS_RETENTION_DAYS = int(os.environ.get("POSITIONS_RETENTION_DAYS", "7"))
# How often the maintenance service runs retention, and where the last run is recorded
RETENTION_INTERVAL_SECONDS = int(os.environ.get("RETENTION_INTERVAL_SECONDS", "3600"))
OPS_RETENTION_KEY = "ops:retention:last"

# Region of interest, same variables as ingest: [minLon, minLat, maxLon, maxLat]
REGION_BBOX = (
    float(os.environ.get("BBOX_LOMIN", "26.0")),
    float(os.environ.get("BBOX_LAMIN", "39.5")),
    float(os.environ.get("BBOX_LOMAX", "31.5")),
    float(os.environ.get("BBOX_LAMAX", "42.0")),
)
# An aircraft counts as "live" if aircraft_latest saw it this recently (ICD §6.2)
LIVE_WINDOW_SECONDS = 60
INGEST_METRICS_URL = os.environ.get("INGEST_METRICS_URL", "http://ingest:8080/metrics")
GEOFENCES_CHANGED_CHANNEL = os.environ.get("GEOFENCES_CHANGED_CHANNEL", "geofences.changed")
# Published by ingest (ICD §4); the name is fixed on the Go side
POSITIONS_CHANNEL = "positions.batch"

# Relay -> WebSocket consumers (ICD §5). Same Redis as everything else; Channels keys
# live under their own "asgi" prefix.
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        # redis-py 8 defaults socket_timeout to 5 s, exactly channels-redis' BZPOPMIN wait:
        # an idle consumer's read timed out and dropped the socket. Must stay > 5 s.
        "CONFIG": {"hosts": [{"address": REDIS_URL, "socket_timeout": 15}]},
    }
}
LIVE_GROUP = "live"
WS_HEARTBEAT_SECONDS = 15
# Queued geofence events/heartbeats per socket before a stuck client is disconnected
WS_MAX_QUEUED_MESSAGES = 1000

# Region DEM (COG, EPSG:4326) written by `make dem`, mounted read-only into the backend
TERRAIN_DEM_PATH = os.environ.get("TERRAIN_DEM_PATH", "/srv/dem/dem_4326_cog.tif")

REST_FRAMEWORK = {
    # Read-only public data plus demo geofence editing: no accounts in this project.
    # No authentication classes also means no SessionAuthentication, hence no CSRF
    # check on POST/PATCH/DELETE for browsers that happen to hold an admin session.
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "UNAUTHENTICATED_USER": None,
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "EXCEPTION_HANDLER": "hezarfen.api.errors.exception_handler",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Hezarfen API",
    "DESCRIPTION": "Live air traffic and geospatial data for the Marmara region (ICD §7).",
    "VERSION": "1.3.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
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
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    # prod: hashed, compressed files built by collectstatic in the image
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
        if not DEBUG
        else "django.contrib.staticfiles.storage.StaticFilesStorage"
    },
}
# dev: serve straight from app directories, no collectstatic needed
WHITENOISE_USE_FINDERS = DEBUG
WHITENOISE_AUTOREFRESH = DEBUG

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "plain": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "plain"},
    },
    "root": {"handlers": ["console"], "level": os.environ.get("DJANGO_LOG_LEVEL", "INFO")},
}
