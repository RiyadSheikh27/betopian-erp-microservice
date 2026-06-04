from pathlib import Path
from decouple import config
from datetime import timedelta

""" Build paths inside the project like this: BASE_DIR / 'subdir'."""

BASE_DIR = Path(__file__).resolve().parent.parent


""" Quick-start development settings - unsuitable for production """

SECRET_KEY = config("SECRET_KEY", default="dev-secret-key-change-in-production")
DEBUG = config("DEBUG", default=True, cast=bool)
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="*").split(",")


""" Application definition """

INSTALLED_APPS = [
    "unfold.contrib.filters",
    "unfold.contrib.forms",
    "jazzmin",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party apps
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "drf_spectacular",
    # Local apps
    "apps.apis",
    "apps.utils",
    "apps.authentication",
    "apps.contents",
    "apps.feed",
    "apps.interactions",
    "apps.mom",
    "apps.ebook",
    "apps.chat",
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
        "DIRS": [
            BASE_DIR / "templates",
        ],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


""" Local Database - SQLite """

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

""" Production Database - PostgreSQL """

# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.postgresql',
#         'NAME': 'betopian_db',
#         'USER': 'betopian_user',
#         'PASSWORD': 'betopian@123',
#         'HOST': 'localhost',
#         'PORT': '5432',
#     }
# }


""" Password validation """

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


""" Internationalization """

LANGUAGE_CODE = "en-us"

TIME_ZONE = "Asia/Dhaka"

USE_I18N = True
USE_TZ = True


""" Static files (CSS, JavaScript, Images) """

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

""" Default primary key field type """

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "authentication.User"

""" Rest Framework """

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "apps.authentication.backends.CentralTokenAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_RENDERER_CLASSES": ("rest_framework.renderers.JSONRenderer",),
    "DEFAULT_PARSER_CLASSES": (
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.MultiPartParser",
        "rest_framework.parsers.FormParser",
    ),
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": config("THROTTLE_ANON", default="60/minute"),
        "user": config("THROTTLE_USER", default="300/minute"),
        "auth": config("THROTTLE_AUTH", default="10/minute"),  # login/logout
        "upload": config("THROTTLE_UPLOAD", default="30/minute"),  # post/reel create
        "feed": config("THROTTLE_FEED", default="120/minute"),  # feed reads
        "interactions": config(
            "THROTTLE_INTERACTIONS", default="60/minute"
        ),  # like/comment
    },
}

""" Max file size - 50 MB """

IMAGE_UPLOAD_MAX_SIZE_MB = config("IMAGE_UPLOAD_MAX_SIZE_MB", default=10, cast=int)
VIDEO_UPLOAD_MAX_SIZE_MB = config("VIDEO_UPLOAD_MAX_SIZE_MB", default=200, cast=int)

IMAGE_UPLOAD_MAX_SIZE = IMAGE_UPLOAD_MAX_SIZE_MB * 1024 * 1024
VIDEO_UPLOAD_MAX_SIZE = VIDEO_UPLOAD_MAX_SIZE_MB * 1024 * 1024

# Global Settings
DATA_UPLOAD_MAX_MEMORY_SIZE = VIDEO_UPLOAD_MAX_SIZE
FILE_UPLOAD_MAX_MEMORY_SIZE = VIDEO_UPLOAD_MAX_SIZE

""" Image Compression - Pillow settings """

IMAGE_COMPRESSION_QUALITY = config("IMAGE_COMPRESSION_QUALITY", default=85, cast=int)
IMAGE_MAX_DIMENSION = config("IMAGE_MAX_DIMENSION", default=1920, cast=int)  # max width or height px
AVATAR_MAX_DIMENSION = config("AVATAR_MAX_DIMENSION", default=400,  cast=int)

""" Message Media Size Limits """

DOC_MAX_SIZE = config("DOC_MAX_SIZE", default=50 * 1024 * 1024, cast=int)  # 50 MB
IMAGE_MAX_SIZE = config("IMAGE_MAX_SIZE", default=10 * 1024 * 1024, cast=int)  # 10 MB
VIDEO_MAX_SIZE = config("VIDEO_MAX_SIZE", default=200 * 1024 * 1024, cast=int)  # 200 MB

""" Gunicorn — recommended settings for production (used in gunicorn.conf.py) """

GUNICORN_WORKERS = config("GUNICORN_WORKERS", default=4, cast=int)  # CPU cores * 2 + 1
GUNICORN_THREADS = config("GUNICORN_THREADS", default=2, cast=int)
GUNICORN_TIMEOUT = config("GUNICORN_TIMEOUT", default=120, cast=int)
GUNICORN_KEEPALIVE = config("GUNICORN_KEEPALIVE", default=5, cast=int)

""" Logging - structured console output, descriptive for terminal debugging """

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{asctime}] {levelname} {name} {module}.{funcName}:{lineno} — {message}",
            "style": "{",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "simple": {
            "format": "[{asctime}] {levelname} — {message}",
            "style": "{",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "loggers": {
        "apps.authentication": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": False,
        },
        "apps.contents": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": False,
        },
        "django": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        "django.request": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
    },
}

""" DRF Spectacular settings for API schema generation """

SPECTACULAR_SETTINGS = {
    "TITLE": "Social Media ERP API",
    "DESCRIPTION": "Social Media microservice — part of the ERP system.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SWAGGER_UI_SETTINGS": {
        "persistAuthorization": True,
    },
    "SECURITY": [{"bearerAuth": []}],
    "COMPONENTS": {
        "securitySchemes": {
            "bearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
            }
        }
    },
}

""" Cache - Redis Backend """

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": config("REDIS_URL", default="redis://127.0.0.1:6379/1"),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "SOCKET_CONNECT_TIMEOUT": 5,
            "SOCKET_TIMEOUT": 5,
            "IGNORE_EXCEPTIONS": True,  # never crash the app if Redis is down
        },
        "KEY_PREFIX": "social_erp",
    }
}


"""Simple and classic Jazzmin admin interface settings"""

JAZZMIN_SETTINGS = {
    "site_title": "Betopian Admin",
    "site_header": "Betopian Administration",
    "site_brand": "Betopian",
    "custom_css": "admin/css/betopian.css",
    "custom_js": "admin/js/betopian.js",
    "show_sidebar": True,
    "navigation_expanded": False,
    "order_with_respect_to": [
        "auth",
        "auth.user",
        "auth.group",
    ],
    "icons": {
        "auth": "fas fa-users-cog",
        "auth.user": "fas fa-user",
        "auth.group": "fas fa-users",
    },
    "custom_links": {
        "auth": [
            {
                "name": "Main Website",
                "url": "/",
                "icon": "fas fa-home",
            }
        ]
    },
    "related_modal_active": True,
    "show_ui_builder": False,
}

JAZZMIN_UI_TWEAKS = {
    "theme": "flatly",
    "navbar": "navbar-light",
    "sidebar": "sidebar-light-primary",
    "accent": "accent-primary",
    "brand_colour": False,
    "sidebar_nav_small_text": False,
    "sidebar_disable_expand": False,
    "sidebar_nav_child_indent": True,
    "sidebar_nav_compact_style": True,
    "theme_switcher": False,
    "actions_sticky_top": True,
    "navigation_expanded": True,
}

""" Debugging Third Party Site"""

import sentry_sdk

sentry_sdk.init(
    dsn="https://73fd8f8695bcbc9e7ea3441bb120546c@o4511380585250816.ingest.us.sentry.io/4511380587216896",
    send_default_pii=True,
)
