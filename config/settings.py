import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv()

LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)


def env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


SECRET_KEY = os.getenv("SECRET_KEY")

DEBUG = env_bool("DEBUG", default=False)
ENABLE_HTTPS_SECURITY = env_bool("ENABLE_HTTPS_SECURITY", default=False)

ALLOWED_HOSTS = [
    "localhost",
    "127.0.0.1",
    "192.168.8.180",
    "192.168.8.122",
    "192.168.0.96",
    "medcenter-server",
]


CSRF_TRUSTED_ORIGINS = [
    "http://192.168.8.180:8080",
    "http://192.168.8.180",
    "http://192.168.8.122",
    "http://medcenter.local",
]

# Safe for the current HTTP-only production.
# Enable HTTPS-specific protection later by setting ENABLE_HTTPS_SECURITY=true.
SECURE_SSL_REDIRECT = ENABLE_HTTPS_SECURITY
SESSION_COOKIE_SECURE = ENABLE_HTTPS_SECURITY
CSRF_COOKIE_SECURE = ENABLE_HTTPS_SECURITY
SESSION_COOKIE_HTTPONLY = True
SECURE_HSTS_SECONDS = 31536000 if ENABLE_HTTPS_SECURITY else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = ENABLE_HTTPS_SECURITY
SECURE_HSTS_PRELOAD = ENABLE_HTTPS_SECURITY
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "timetable",
    "users",
    "patients",
    "appointments",
    "treatment",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
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
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "timetable.context_processors.user_permissions",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DATABASE_NAME"),
        "USER": os.getenv("DATABASE_USER"),
        "PASSWORD": os.getenv("DATABASE_PASSWORD"),
        "HOST": os.getenv("DATABASE_HOST", "localhost"),
        "PORT": os.getenv("DATABASE_PORT", "5432"),
    }
}


AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LANGUAGE_CODE = "ru-RU"

TIME_ZONE = "Europe/Moscow"

USE_I18N = True

USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = (BASE_DIR / "static",)
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "users.User"

LOGIN_REDIRECT_URL = "/"

LOGOUT_REDIRECT_URL = "/"


USE_L10N = True

DATE_FORMAT = "d.m.Y"
DATETIME_FORMAT = "d.m.Y H:i"
TIME_FORMAT = "H:i"

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "unique-snowflake",
        "TIMEOUT": 300,
    }
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {name} {module} | {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} | {name} | {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
        "app_file": {
            "class": "logging.FileHandler",
            "filename": LOGS_DIR / "app.log",
            "formatter": "verbose",
            "encoding": "utf-8",
        },
        "errors_file": {
            "class": "logging.FileHandler",
            "filename": LOGS_DIR / "errors.log",
            "formatter": "verbose",
            "level": "ERROR",
            "encoding": "utf-8",
        },
        "appointments_file": {
            "class": "logging.FileHandler",
            "filename": LOGS_DIR / "appointments.log",
            "formatter": "verbose",
            "encoding": "utf-8",
        },
        "treatment_file": {
            "class": "logging.FileHandler",
            "filename": LOGS_DIR / "treatment.log",
            "formatter": "verbose",
            "encoding": "utf-8",
        },
    },
    "root": {
        "handlers": ["console", "app_file", "errors_file"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console", "app_file", "errors_file"],
            "level": "INFO",
            "propagate": False,
        },
        "django.request": {
            "handlers": ["console", "errors_file"],
            "level": "ERROR",
            "propagate": False,
        },
        "appointments": {
            "handlers": ["console", "appointments_file", "errors_file"],
            "level": "INFO",
            "propagate": False,
        },
        "treatment": {
            "handlers": ["console", "treatment_file", "errors_file"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
