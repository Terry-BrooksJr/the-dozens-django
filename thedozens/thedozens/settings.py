# -*- coding: utf-8 -*-
"""
Django settings for thedozens project.

Generated by 'django-admin startproject' using Django 4.2.6.


"""
from pathlib import Path
from dotenv import load_dotenv
import os
from datetime import datetime
from django.core.mail import send_mail
from datetime import datetime
from loguru import logger
from logtail import LogtailHandler

load_dotenv(override=True)
GLOBAL_NOW = datetime.now()


# SECTION - Application definition
ROOT_URLCONF = "thedozens.urls"
WSGI_APPLICATION = "thedozens.wsgi.application"
BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.getenv("SECRET_KEY")
DEBUG = True
ADMINS = [("Terry Brooks", "Terry@BrooksJr.com")]
ALLOWED_HOSTS = ["*"]
INSTALLED_APPS = [
    # Django-Installed Apps
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-Party Apps
    "rest_framework",
    "django_filters",
    "debug_toolbar",
    "graphene_django",
    "rest_framework_swagger",
    "crispy_forms",
    "crispy_bootstrap5",
    "cacheops",
    "django_prometheus",
    # Project Apps
    "API",
    "graphQL",
]
LANGUAGE_CODE = "en-us"
TIME_ZONE = "America/New_York"
USE_I18N = True
USE_TZ = True
MIDDLEWARE = [
    "kolo.middleware.KoloMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "debug_toolbar.middleware.DebugToolbarMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


#!SECTION

# SECTION - Database and Caching
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql_psycopg2",
        "NAME": os.getenv("POSTGRES_DB"),
        "USER": os.getenv("POSTGRES_USER"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD"),
        "HOST": os.getenv("PG_DATABASE_HOST"),
        "PORT": os.getenv("PG_DATABASE_PORT")
        # "OPTIONS": {"sslmode": "require"},
    }
}
CACHEOPS_CLIENT_CLASS = "django_redis.client.DefaultClient"

CACHEOPS_REDIS = os.getenv("REDIS_CACHE_URI")
CACHEOPS = {
    # Automatically cache any User.objects.get() calls for 15 minutes
    # This also includes .first() and .last() calls,
    # as well as request.user or post.author access,
    # where Post.author is a foreign key to auth.User
    "auth.user": {"ops": "get", "timeout": 60 * 15},
    # Automatically cache all gets and queryset fetches
    # to other django.contrib.auth models for an hour
    "auth.*": {"ops": {"fetch", "get"}, "timeout": 60 * 60},
    # Cache all queries to Permission
    # 'all' is an alias for {'get', 'fetch', 'count', 'aggregate', 'exists'}
    "auth.permission": {"ops": "all", "timeout": 60 * 60},
    # And since ops is empty by default you can rewrite last line as:
    # "Insult.objects.filter(status='A').cache(ops=['get'])": {'timeout': 60*60},
    # NOTE: binding signals has its overhead, like preventing fast mass deletes,
    #       you might want to only register whatever you cache and dependencies.
    "API.*": {"ops": ("get"), "timeout": 60 * 60},
    # Finally you can explicitely forbid even manual caching with:
    "some_app.*": None,
}
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": os.getenv("REDIS_CACHE_URI"),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
    }
}

CACHEOPS_DEGRADE_ON_FAILURE = True
CACHEOPS_ENABLED = True
#!SECTION

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
        "rest_framework.parsers.FormParser",
        "rest_framework.parsers.MultiPartParser",
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
    ],
}

#!SECTION

# SECTION - Email Settings (Django-Mailer)

EMAIL_BACKEND = "mailer.backend.DbBackend"
MAILER_EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.getenv("EMAIL_SERVER")
EMAIL_USE_TLS = True
EMAIL_PORT = os.getenv("EMAIL_TSL_PORT")
EMAIL_HOST_USER = os.getenv("NOTIFICATION_SENDER_EMAIL")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_ACCT_PASSWORD")
MAILER_EMPTY_QUEUE_SLEEP = os.getenv("MAILER_EMPTY_QUEUE_SLEEP")
# !SECTION

#  SECTION - GraphQL Settings (Graphene-Django)

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
