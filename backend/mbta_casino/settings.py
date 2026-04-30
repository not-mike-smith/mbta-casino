from pathlib import Path
import os
import structlog
from dotenv import load_dotenv
import dj_database_url

# BASE_DIR is backend/. The .env file lives one level up at the repo root.
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR.parent / ".env")

# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------

SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]

DEBUG = os.environ.get("DJANGO_DEBUG", "false").lower() == "true"

ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost 127.0.0.1").split()

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

ROOT_URLCONF = "mbta_casino.urls"

WSGI_APPLICATION = "mbta_casino.wsgi.application"

# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.sessions",
    "rest_framework",
    "corsheaders",
    "users",
    "betting",
    "mbta",
    "stations",
]

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

# CorsMiddleware must appear before CommonMiddleware.
MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
]

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

DATABASES = {
    "default": dj_database_url.config(
        env="DATABASE_URL",
        conn_max_age=600,
    )
}

# ---------------------------------------------------------------------------
# Sessions (cookie-based auth)
# ---------------------------------------------------------------------------

SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = not DEBUG       # HTTPS only in production
SESSION_COOKIE_SAMESITE = "Lax"
# Set to ".yourdomain.com" in production so the cookie is shared across
# subdomains (e.g. app.yourdomain.com + api.yourdomain.com).
SESSION_COOKIE_DOMAIN = os.environ.get("SESSION_COOKIE_DOMAIN") or None

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

# Space-separated list of allowed origins, e.g. "http://localhost:5173"
CORS_ALLOWED_ORIGINS = os.environ.get(
    "CORS_ALLOWED_ORIGINS", "http://localhost:5173"
).split()
# Credentials (cookies) must be explicitly allowed for cross-origin requests.
CORS_ALLOW_CREDENTIALS = True

# ---------------------------------------------------------------------------
# Templates (minimal — required for DRF browsable API in development)
# ---------------------------------------------------------------------------

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
            ],
        },
    },
]

# ---------------------------------------------------------------------------
# Internationalisation
# ---------------------------------------------------------------------------

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = False
USE_TZ = True  # all timestamps are timezone-aware

# ---------------------------------------------------------------------------
# Business rules
#
# These are application-level settings, not DB constraints. Changing them
# requires only a redeploy, not a migration.
# ---------------------------------------------------------------------------

# MBTA v3 API key. Optional for low-volume local dev; required in production.
# Get one at https://api-v3.mbta.com/
MBTA_API_KEY: str = os.environ.get("MBTA_API_KEY", "")

# How many minutes before predicted arrival a prediction stops being bettable.
BETTING_WINDOW_MINUTES: int = int(os.environ.get("BETTING_WINDOW_MINUTES", "2"))

# Arrival within this many seconds of the predicted time resolves as a PUSH.
PUSH_TOLERANCE_SECONDS: int = int(os.environ.get("PUSH_TOLERANCE_SECONDS", "30"))

# ---------------------------------------------------------------------------
# Structured logging (structlog)
#
# structlog is the Python equivalent of .NET's structured logging.
# bind_contextvars() is the equivalent of a logging scope — call it once
# (e.g. in middleware) and those key-value pairs appear on every subsequent
# log line within that context without passing them around manually.
#
# In development (DEBUG=True) logs are pretty-printed to the console.
# In production (DEBUG=False) logs are JSON, one object per line.
# ---------------------------------------------------------------------------

structlog.configure(
    processors=[
        # Merges any values bound via structlog.contextvars.bind_contextvars().
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.ExceptionRenderer(),
        structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "dev" if DEBUG else "json",
        },
    },
    "formatters": {
        # Human-readable coloured output for local development.
        "dev": {
            "()": structlog.stdlib.ProcessorFormatter,
            "processor": structlog.dev.ConsoleRenderer(),
        },
        # Machine-readable JSON for production / CloudWatch.
        "json": {
            "()": structlog.stdlib.ProcessorFormatter,
            "processor": structlog.processors.JSONRenderer(),
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
