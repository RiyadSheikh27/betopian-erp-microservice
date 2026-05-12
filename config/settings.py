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
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


""" Database """

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}


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
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_RENDERER_CLASSES": (
        "rest_framework.renderers.JSONRenderer",
    ),
    "DEFAULT_PARSER_CLASSES": (
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.MultiPartParser",
        "rest_framework.parsers.FormParser",
    ),
}

# SIMPLE_JWT = {
#     "ACCESS_TOKEN_LIFETIME": timedelta(hours=24),
#     "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
#     "ROTATE_REFRESH_TOKENS": True,
#     "BLACKLIST_AFTER_ROTATION": True,
#     "AUTH_HEADER_TYPES": ("Bearer",),
# }

""" Max file size - 50 MB """

DATA_UPLOAD_MAX_MEMORY_SIZE = 52428800
FILE_UPLOAD_MAX_MEMORY_SIZE = 52428800


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
        # App-level loggers
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
        # Django internals — only warnings and above to keep terminal clean
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

"""Simple and classic Jazzmin admin interface settings"""
JAZZMIN_SETTINGS = {
    # Basic branding
    "site_title": "Admin Panel",
    "site_header": "Administration",
    "site_brand": "Admin",
    "welcome_sign": "Welcome to Admin Panel",
    "copyright": "Your Company",
    
    # Simple search options
    "search_model": ["auth.User", "auth.Group"],
    
    # Clean top menu links
    "topmenu_links": [
        {"name": "Dashboard", "url": "admin:index", "permissions": ["auth.view_user"]},
        {"model": "auth.User"},
        {"model": "auth.Group"},
    ],
    
    # Basic icons
    "icons": {
        "auth": "fas fa-users",
        "auth.user": "fas fa-user",
        "auth.group": "fas fa-users",
    },
    
    # Keep it simple
    "default_icon_parents": "fas fa-chevron-circle-right",
    "default_icon_children": "fas fa-circle",
    
    # Modal for related fields
    "related_modal_active": True,
    
    # Simple form layout
    "changeform_format": "single",
    
    # Don't show UI builder
    "show_ui_builder": False,
    
    # Show sidebar
    "show_sidebar": True,
    
    # Classic light theme
    "theme": "flatly",
}

JAZZMIN_UI_TWEAKS = {
    # Clean, simple theme
    "theme": "flatly",
    
    # Light navbar
    "navbar": "navbar-light bg-light",
    
    # Simple accent
    "accent": "accent-primary",
    
    # Light sidebar
    "sidebar": "sidebar-light-primary",
    
    # Brand color
    "brand_colour": "navbar-light",
    
    # Disable dark mode toggle
    "theme_switcher": False,
    
    # Keep navigation simple
    "sidebar_nav_small_text": False,
    "sidebar_disable_expand": False,
}