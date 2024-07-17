# -*- coding: utf-8 -*-
"""
Django settings for thedozens project.

Generated by 'django-admin startproject' using Django 4.2.6.


"""
from pathlib import Path
import os
import sys
from datetime import datetime
from pathlib import Path

from logtail import LogtailHandler
import sys
from loguru import logger

GLOBAL_NOW = datetime.now()

LOGGING_CONFIG = None

# SECTION - Application definition
ROOT_URLCONF = "thedozens.urls"
WSGI_APPLICATION = "thedozens.wsgi.application"
BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.environ["SECRET_KEY"]
DEBUG = True
ADMINS = [("Terry Brooks", "Terry@BrooksJr.com")]
ALLOWED_HOSTS = ["*"]
INSTALLED_APPS = [
    # Django-Installed Apps
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.sites",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-Party Apps
 
    "rest_framework",
    "django_filters",
    "debug_toolbar",
    "graphene_django",
    "djoser",
    "djoser.webauthn",
    "crispy_forms",
    "captcha",
    "crispy_bootstrap5",
    "django_prometheus",
    "drf_spectacular",
    "asymmetric_jwt_auth",
    "certbot_django.server",
    # Project Apps
    "API",
    "graphQL",
]
PRIMARY_LOG_FILE = os.path.join(BASE_DIR, "standup", "logs", "primary_ops.log")
CRITICAL_LOG_FILE = os.path.join(BASE_DIR, "standup", "logs", "fatal.log")
DEBUG_LOG_FILE = os.path.join(BASE_DIR, "standup", "logs", "utility.log")
LOGTAIL_HANDLER = LogtailHandler(source_token=os.getenv("LOGTAIL_API_KEY"))

logger.add(DEBUG_LOG_FILE, diagnose=True, catch=True, backtrace=True, level="DEBUG")
logger.add(PRIMARY_LOG_FILE, diagnose=False, catch=True, backtrace=False, level="INFO")
logger.add(LOGTAIL_HANDLER, diagnose=False, catch=True, backtrace=False, level="INFO")

LANGUAGE_CODE = "en-us"
TIME_ZONE = "America/Chicago"
USE_I18N = True
USE_TZ = True
MIDDLEWARE = [
    "kolo.middleware.KoloMiddleware",
    'django_prometheus.middleware.PrometheusBeforeMiddleware',
        "django.middleware.cache.UpdateCacheMiddleware",
        # "django.middleware.cache.UpdateCacheMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "debug_toolbar.middleware.DebugToolbarMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "asymmetric_jwt_auth.middleware.JWTAuthMiddleware",
        "django.middleware.cache.FetchFromCacheMiddleware",

    'django_prometheus.middleware.PrometheusAfterMiddleware'
    # "django.middleware.cache.FetchFromCacheMiddleware",
]
RECAPTCHA_PRIVATE_KEY = os.getenv("RECAPTCHA_PRIVATE_KEY")
RECAPTCHA_PUBLIC_KEY = os.getenv("RECAPTCHA_PUBLIC_KEY")

#!SECTION

# SECTION - Database and Caching
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
DATABASES = {
    "default": {
        "ENGINE": "django_cockroachdb",
        "NAME": os.environ["POSTGRES_DB"],
        "USER": os.environ["PG_DATABASE_USER"],
        "PASSWORD": os.environ["PG_DATABASE_PASSWORD"],
        "HOST": os.environ["PG_DATABASE_HOST"],
        "PORT": os.environ["PG_DATABASE_PORT"],
        "OPTIONS": {"sslmode": "verify-full"},
    }
}


CACHES = {
    "default": {
        "BACKEND": "django_prometheus.cache.backends.redis.RedisCache",
        "LOCATION": os.getenv("REDIS_CACHE_URI"),
    }
}

CACHE_MIDDLEWARE_ALIAS = "default"
CACHE_MIDDLEWARE_SECONDS = 300
CACHE_MIDDLEWARE_KEY_PREFIX = "yo-mama"

CACHE_MIDDLEWARE_ALIAS = "default"
CACHE_MIDDLEWARE_SECONDS = 300
CACHE_MIDDLEWARE_KEY_PREFIX = "thedozens_cache"

#!SECTION

#  SECTION - Applicatiom Preformance Mointoring
PROMETHEUS_LATENCY_BUCKETS = (
    0.01,
    0.025,
    0.05,
    0.075,
    0.1,
    0.25,
    0.5,
    0.75,
    1.0,
    2.5,
    5.0,
    7.5,
    10.0,
    25.0,
    50.0,
    75.0,
    float("inf"),
)
PROMETHEUS_LATENCY_BUCKETS = (
    0.1,
    0.2,
    0.5,
    0.6,
    0.8,
    1.0,
    2.0,
    3.0,
    4.0,
    5.0,
    6.0,
    7.5,
    9.0,
    12.0,
    15.0,
    20.0,
    30.0,
    float("inf"),
)


# !SECTION


# SECTION - Password validatio and User Authentication

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
AUTHENTICATION_BACKENDS = [
     'django.contrib.auth.backends.ModelBackend',
     'allauth.account.auth_backends.AuthenticationBackend',
 ]

#!SECTION


# SECTION - Static files & Templates
logger.debug(BASE_DIR)
template_dir = [
    os.path.join(BASE_DIR, "templates"),
]
INTERNAL_IPS = [
    "127.0.0.1",
]
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": template_dir,
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

STATIC_URL = "static/"
STATICFILES_DIRS = [
    BASE_DIR / "static",
]
STATIC_ROOT = BASE_DIR / "staticfiles/"
#!SECTION

# SECTION - DRF Settings
REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.DjangoModelPermissionsOrAnonReadOnly"
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 15,
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
    ],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',

}

#!SECTION
SPECTACULAR_SETTINGS = {
     'TITLE': 'Yo\' MaMa - The Roast API',
    'DESCRIPTION': 'Robust REST API with rate limits for Yo Mama Jokes , that allows API Consumers to filter jokes based on Category and/or Explicitly ',
    'VERSION': '2.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    "SWAGGER_UI_SETTINGS": {
        "deepLinking": True,
        "persistAuthorization": True,
        "displayOperationId": True,
    },
    "SWAGGER_UI_DIST": "https://cdn.jsdelivr.net/npm/swagger-ui-dist@latest", # default
    "SWAGGER_UI_FAVICON_HREF": "https://cdn.jsdelivr.net/gh/Terry-BrooksJr/MindHealthCDN@94065f369600b5ac3fd17c56da7800c83bf356dd/images/yoyoo_400x400.jpg", # default is swagger favicon
    "ENUM_ADD_EXPLICIT_BLANK_NULL_CHOICE": True,
    
   }
# SECTION - Email Settings (Django-Mailer)

EMAIL_BACKEND = "mailer.backend.DbBackend"
MAILER_EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.environ["EMAIL_SERVER"]
EMAIL_USE_TLS = True
EMAIL_PORT = os.environ["EMAIL_TSL_PORT"]
EMAIL_HOST_USER = os.environ["NOTIFICATION_SENDER_EMAIL"]
EMAIL_HOST_PASSWORD = os.environ["EMAIL_ACCT_PASSWORD"]
MAILER_EMPTY_QUEUE_SLEEP = os.environ["MAILER_EMPTY_QUEUE_SLEEP"]
# !SECTION

#  SECTION - GraphQL Settings (Graphene-Django)``

GRAPHENE = {
    "SCHEMA": "graphQL.schema.schema",
    "MIDDLEWARE": [
        "graphene_django.debug.DjangoDebugMiddleware",
    ],
}

# !SECTION

# SECTION - Form Rendering Settings (Crispy Forms)
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"

CRISPY_TEMPLATE_PACK = "bootstrap5"
# !SECTION

PRIMARY_LOG_FILE = os.path.join( BASE_DIR, "standup", "logs", "primary_ops.log")
CRITICAL_LOG_FILE = os.path.join( BASE_DIR, "standup", "logs", "fatal.log")
DEBUG_LOG_FILE = os.path.join( BASE_DIR, "standup", "logs", "utility.log")
LOGTAIL_HANDLER = LogtailHandler(source_token=os.environ["LOGTAIL_API_KEY"])
DEFAULT_HANDLER = sys.stdout


logger.add(DEBUG_LOG_FILE, diagnose=True, catch=True, backtrace=True, level="DEBUG")
logger.add(PRIMARY_LOG_FILE, diagnose=False, catch=True, backtrace=False, level="INFO")
logger.add(LOGTAIL_HANDLER, diagnose=False, catch=True, backtrace=False, level="INFO")
logger.add(DEFAULT_HANDLER, diagnose=False, catch=True, backtrace=False, level="DEBUG")

PRIMARY_LOG_FILE = os.path.join(BASE_DIR, "logs", "primary_ops.log")
CRITICAL_LOG_FILE = os.path.join(BASE_DIR, "logs", "fatal.log")
DEBUG_LOG_FILE = os.path.join(BASE_DIR, "logs", "utility.log")
LOGTAIL_HANDLER = LogtailHandler(source_token=os.environ["LOGTAIL_API_KEY"])
DEFAULT_HANDLER = sys.stdout

logger.add(DEBUG_LOG_FILE, diagnose=True, catch=True, backtrace=True, level="DEBUG")
logger.add(DEFAULT_HANDLER, diagnose=True, catch=True, backtrace=True, level="DEBUG")
logger.add(PRIMARY_LOG_FILE, diagnose=False, catch=True, backtrace=False, level="INFO")
logger.add(LOGTAIL_HANDLER, diagnose=False, catch=True, backtrace=False, level="INFO")