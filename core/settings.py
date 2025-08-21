"""
module: core.settings

Django settings for thedozens project.

"""

import json
import os
import sys
import warnings
from datetime import datetime
from pathlib import Path

import highlight_io
from configurations import Configuration, values
from highlight_io.integrations.django import DjangoIntegration
from loguru import logger


def log_warning(
    message: str, category, filename: str, lineno: str, file=None, line=None
) -> None:
    logger.warning(f"{filename}:{lineno} - {category.__name__}: {message}")


NSFW_WORD_LIST_URI = values.URLValue(
    environ=True, environ_prefix=None, environ_name="NSFW_WORD_LIST_URI"
)
GLOBAL_NOW = datetime.now()

BASE_DIR = values.PathValue(
    Path(__file__).resolve().parent.parent.parent, environ=False
)


class Base(Configuration):
    # SECTION Start - Application definition
    SECRET_KEY = values.SecretValue(
        environ=True, environ_prefix=None, environ_name="SECRET_KEY"
    )
    SITE_ID = values.PositiveIntegerValue(
        environ=True, environ_prefix=None, environ_name="SITE_ID"
    )

    ROOT_URLCONF = values.Value("core.urls", environ=False)
    WSGI_APPLICATION = values.Value("core.wsgi.application", environ=False)

    ADMINS = values.ListValue([("Terry Brooks", "Terry@BrooksJr.com")], environ=False)
    LANGUAGE_CODE = values.Value("en-us", environ=False)
    APPEND_SLASH = values.BooleanValue(True, environ=False)
    VIEW_CACHE_TTL = values.PositiveIntegerValue(
        environ=True, environ_prefix=None, environ_name="CACHE_TTL"
    )
    SESSION_ENGINE = "django.contrib.sessions.backends.cache"
    SESSION_CACHE_ALIAS = "default"
    TIME_ZONE = values.Value("America/Chicago", environ=False)
    USE_I18N = values.BooleanValue(True, environ=False)
    USE_TZ = values.BooleanValue(True, environ=False)
    DEFAULT_AUTO_FIELD = values.Value("django.db.models.BigAutoField", environ=False)

    RECAPTCHA_PRIVATE_KEY = values.SecretValue(
        environ=True, environ_prefix=None, environ_name="RECAPTCHA_PRIVATE_KEY"
    )
    RECAPTCHA_PUBLIC_KEY = values.SecretValue(
        environ=True, environ_prefix=None, environ_name="RECAPTCHA_PUBLIC_KEY"
    )
    CRISPY_ALLOWED_TEMPLATE_PACKS = (
        "bootstrap",
        "uni_form",
        "bootstrap5",
        "bootstrap4",
    )
    CRISPY_TEMPLATE_PACK = "bootstrap5"
    #!SECTION END - Application definition

    # SECTION Start - Media, Files and Static Assests Storage

    #!SECTION End - Media, Files and Static Assests Storage

    # SECTION Start- Logging
    LOG_FORMAT = "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <bold><level>{message}</level></bold>"
    DEFAULT_LOGGER_CONFIG = {
        "format": LOG_FORMAT,
        "diagnose": False,
        "catch": True,
        "backtrace": False,
        "serialize": True,
    }
    PRIMARY_LOG_FILE = Path(
        os.path.join(BASE_DIR, "logs", "primary_ops.log")
    )  # pyrefly: ignore
    CRITICAL_LOG_FILE = Path(
        os.path.join(BASE_DIR, "logs", "fatal.log")
    )  # pyrefly: ignore
    DEBUG_LOG_FILE = Path(
        os.path.join(BASE_DIR, "logs", "utility.log")
    )  # pyrefly: ignore
    DEFAULT_HANDLER = sys.stdout
    logger.remove()

    warnings.filterwarnings("default")
    warnings.showwarning = log_warning
    #!SECTION END - Logging
    DATABASES = values.DictValue(
        {
            "default": {
                "ENGINE": "django.db.backends.postgresql",
                "NAME": os.getenv("POSTGRES_DB"),
                "USER": os.getenv("PG_DATABASE_USER"),
                "PASSWORD": os.getenv("PG_DATABASE_PASSWORD"),
                "HOST": os.getenv("PG_DATABASE_HOST"),
                "DISABLE_SERVER_SIDE_CURSORS": True,
                "PORT": os.getenv("PG_DATABASE_PORT"),
            "pool": {
                "max_size": 11,
                "name": "django-thedozens",
                "max_idle": 15,
            }
        }
    }
    )
    # SECTION Start - Static files & Templates
    AWS_ACCESS_KEY_ID = values.SecretValue(
        environ=True, environ_prefix=None, environ_name="DO_SPACES_KEY"
    )
    AWS_SECRET_ACCESS_KEY = values.SecretValue(
        environ=True, environ_prefix=None, environ_name="DO_SPACES_SECRET"
    )
    AWS_STORAGE_BUCKET_NAME = values.SecretValue(
        environ=True, environ_prefix=None, environ_name="DO_SPACES_BUCKET"
    )
    AWS_S3_ENDPOINT_URL = "https://nyc3.digitaloceanspaces.com"
    AWS_REGION_NAME = "nyc3"
    AWS_S3_OBJECT_PARAMETERS = {
        "CacheControl": "max-age=86400",
    }
    AWS_LOCATION = "static"
    STATIC_URL = f"{AWS_S3_ENDPOINT_URL}/{AWS_LOCATION}/"
    STATICFILES_DIRS = [
        os.path.join(BASE_DIR, "the-dozens-django", "static"),  # pyrefly: ignore
    ]
    STATIC_ROOT = os.environ["TEMP_STATIC_DIR"]
    template_dir = values.ListValue(
        [
            Path(os.path.join(BASE_DIR, "the-dozens-django", "templates"))
        ],  # pyrefly: ignore
        environ=False,
    )
    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.s3.S3Storage",
            "OPTIONS": {},
        },
        "staticfiles": {
            "BACKEND": "core.storage_backends.StaticStorage",
            "LOCATION": AWS_LOCATION,
            "AWS_S3_OBJECT_PARAMETERS": {
                "CacheControl": "max-age=86400",
            },
            "AWS_S3_FILE_OVERWRITE": False,
            "AWS_DEFAULT_ACL": "public-read",
            "AWS_REGION_NAME": AWS_REGION_NAME,
            "AWS_S3_ENDPOINT_URL": AWS_S3_ENDPOINT_URL,
        },
        "media": {
            "BACKEND": "core.storage_backends.MediaStorage",
            "LOCATION": "media",
            "AWS_S3_OBJECT_PARAMETERS": {
                "CacheControl": "max-age=86400",
            },
            "AWS_S3_FILE_OVERWRITE": False,
            "AWS_DEFAULT_ACL": "public",
            "AWS_REGION_NAME": AWS_REGION_NAME,
            "AWS_S3_ENDPOINT_URL": AWS_S3_ENDPOINT_URL,
        },
    }
    TEMPLATES = values.ListValue(
        [
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
        ],
        environ=False,
    )

    #!SECTION End - Static files & Templates

    #  SECTION  Start - Application Preformance Mointoring
    PROMETHEUS_LATENCY_BUCKETS = values.TupleValue(
        (
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
        ),
        environ=False,
    )

    PROMETHEUS_METRIC_NAMESPACE = values.Value("dozens_api", environ=False)
    #!SECTION End - Application Preformance Mointoring

    # SECTION Start - Password validation and User Authentication
    AUTH_PASSWORD_VALIDATORS = values.ListValue(
        [
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
        ],
        environ=False,
    )
    AUTHENTICATION_BACKENDS = values.ListValue(
        [
            "django.contrib.auth.backends.ModelBackend",
        ],
        environ=False,
    )
    #!SECTION End - Password validation and User Authentication

    #!SECTION End - Static files & Templates

    # SECTION Start - REST API.SWAGGER DOCUMENTATION SETTINGS
    SPECTACULAR_SETTINGS = {
        "TITLE": "Yo' Mama - The Roast API - Swagger UI",
        "DESCRIPTION": "RESTful implementation of a light hearted Roast Insult API ",
        "VERSION": "1.0.0",
        "SERVE_INCLUDE_SCHEMA": False,
        "SWAGGER_UI_SETTINGS": {
            "deepLinking": True,
            "persistAuthorization": True,
            "displayOperationId": False,
        },
        "SWAGGER_UI_DIST": "https://cdn.jsdelivr.net/npm/swagger-ui-dist@latest",
        "SWAGGER_UI_FAVICON_HREF": "https://cdn.yo-momma.net/staticfiles/assets/yoyoo_400x400.jpg",
        "CONTACT": {
            "name": "Terry A. Brooks, Jr.",
            "url": "https://brooksjr.com",
            "email": "terry@brooksjr.com",
        },
        "EXTERNAL_DOCS": {
            "url": "https://github.com/Terry-BrooksJr/the-dozens-django",
            "description": "GitHub Repository and full API documentation Hub",
        },
    }
    REST_FRAMEWORK_EXTENSIONS = values.DictValue({"DEFAULT_CACHE_ERRORS": False})
    #!SECTION End - REST API.SWAGGER DOCUMENTATION SETTINGS

    #  SECTION Start - GraphQL Settings (Graphene-Django)
    GRAPHENE = values.DictValue(
        {
            "SCHEMA": "applications.graphQL.schema.schema",
            "MIDDLEWARE": [
                "graphene_django.debug.DjangoDebugMiddleware",
            ],
        },
        environ=False,
    )
    #!SECTION End - GraphQL Settings (Graphene-Django)

    # SECTION - Email Settings (Django-Mailer)
    MAILER_EMAIL_BACKEND = values.Value(
        "django.core.mail.backends.smtp.EmailBackend", environ=False
    )
    EMAIL_BACKEND = MAILER_EMAIL_BACKEND
    CACHES = values.DictValue(
        {
            "default": {
                "BACKEND": "django_prometheus.cache.backends.redis.RedisCache",
                "LOCATION": os.environ["REDIS_CACHE_TOKEN"],
                "OPTIONS": {
                    "CLIENT_CLASS": "django_redis.client.DefaultClient",
                },
            },
            "select2": {
                "BACKEND": "django_redis.cache.RedisCache",
                "LOCATION": f"{os.environ['REDIS_CACHE_TOKEN']}/2",
                "OPTIONS": {
                    "CLIENT_CLASS": "django_redis.client.DefaultClient",
                },
            },
        }
    )
    SELECT2_CACHE_BACKEND = "select2"

    EMAIL_HOST = values.Value(
        environ=True, environ_prefix=None, environ_name="EMAIL_SERVER"
    )
    EMAIL_USE_TLS = values.BooleanValue(True, environ=False)
    EMAIL_PORT = values.PositiveIntegerValue(
        environ=True, environ_prefix=None, environ_name="EMAIL_TSL_PORT"
    )
    EMAIL_HOST_USER = values.Value(
        environ=True, environ_prefix=None, environ_name="NOTIFICATION_SENDER_EMAIL"
    )
    EMAIL_HOST_PASSWORD = values.SecretValue(
        environ=True, environ_prefix=None, environ_name="EMAIL_ACCT_PASSWORD"
    )
    MAILER_EMPTY_QUEUE_SLEEP = values.IntegerValue(
        environ=True, environ_prefix=None, environ_name="MAILER_EMPTY_QUEUE_SLEEP"
    )


class Production(Base):
    ALLOWED_HOSTS = values.ListValue(
        environ=True, environ_prefix=None, environ_name="ALLOWED_HOSTS"
    )
    INSTALLED_APPS = values.ListValue(
        [
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
            "rest_framework.authtoken",
            "django_filters",
            "corsheaders",
            "storages",
            "djoser",
            "graphene_django",
            "crispy_forms",
            "crispy_bootstrap5",
            "django_prometheus",
            "drf_spectacular",
            "django_select2",
            # Project Apps
            "applications.API",
            "applications.graphQL",
            "drf_spectacular_sidecar",
        ],
        environ=False,
    )

    MIDDLEWARE = values.ListValue(
        [
            "django_prometheus.middleware.PrometheusBeforeMiddleware",
            # "django.middleware.cache.UpdateCacheMiddleware",
            "django.middleware.security.SecurityMiddleware",
            "whitenoise.middleware.WhiteNoiseMiddleware",
            "django.contrib.sessions.middleware.SessionMiddleware",
            "corsheaders.middleware.CorsMiddleware",
            "django.middleware.common.CommonMiddleware",
            "django.middleware.csrf.CsrfViewMiddleware",
            "django.contrib.auth.middleware.AuthenticationMiddleware",
            "django.contrib.messages.middleware.MessageMiddleware",
            "django.middleware.clickjacking.XFrameOptionsMiddleware",
            # "django.middleware.cache.FetchFromCacheMiddleware",
            "django_prometheus.middleware.PrometheusAfterMiddleware",
        ],
        environ=False,
    )
    DEBUG = values.BooleanValue(False, environ=False)
    CSRF_TRUSTED_ORIGINS = values.ListValue(
        environ=True, environ_prefix=None, environ_name="ALLOWED_ORIGINS"
    )
    CORS_ALLOWED_ORIGINS = json.loads(os.getenv("ALLOWED_ORIGINS"))
    # SECTION Start - Production Database

    #!SECTION End - Database and Caching
    # SECTION Start - DRF Settings
    REST_FRAMEWORK = values.DictValue(
        {
            "DEFAULT_PERMISSION_CLASSES": [
                "rest_framework.permissions.DjangoModelPermissionsOrAnonReadOnly"
            ],
            "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
            "PAGE_SIZE": 10,
            "DEFAULT_RENDERER_CLASSES": [
                "rest_framework.renderers.JSONRenderer",
                "rest_framework.renderers.BrowsableAPIRenderer",
            ],
            "DEFAULT_AUTHENTICATION_CLASSES": (
                "rest_framework.authentication.TokenAuthentication",
            ),
            # "DEFAULT_THROTTLE_CLASSES": [
            #     "rest_framework.throttling.AnonRateThrottle",
            # ],
            "DEFAULT_THROTTLE_RATES": {"anon": "4/minute", "user": "12/minute"},
            "DEFAULT_FILTER_BACKENDS": [
                "django_filters.rest_framework.DjangoFilterBackend",
            ],
            "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
        },
        environ=False,
    )
    #!SECTION End - DRF Settings

    # SECTION Start - Logging

    H = highlight_io.H(
        os.environ["HIGHLIGHT_IO_API_KEY"],
        integrations=[DjangoIntegration()],
        instrument_logging=False,
        service_name="my-app",
        service_version="git-sha",
        environment="production",
    )

    logger.add(
        sink=H.logging_handler, level="INFO", **Base.DEFAULT_LOGGER_CONFIG
    )  # pyrefly: ignore
    logger.add(
        sink=Base.PRIMARY_LOG_FILE, **Base.DEFAULT_LOGGER_CONFIG, level="INFO"
    )  # pyrefly: ignore


class Testing(Base):
    pass


class Offline(Base):
    INTERNAL_IPS = ["*"]
    ALLOWED_HOSTS = ["*"]
    DEBUG = values.BooleanValue(True, environ=False)
    INSTALLED_APPS = values.ListValue(
        [
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
            "rest_framework.authtoken",
            "django_filters",
            "corsheaders",
            "debug_toolbar",
            "storages",
            "djoser",
            "graphene_django",
            "crispy_forms",
            "crispy_bootstrap5",
            "django_prometheus",
            "drf_spectacular",
            "django_select2",
            # Project Apps
            "applications.API",
            "applications.graphQL",
            "drf_spectacular_sidecar",
        ],
        environ=False,
    )

    MIDDLEWARE = values.ListValue(
        [
            "django_prometheus.middleware.PrometheusBeforeMiddleware",
            "django.middleware.cache.UpdateCacheMiddleware",
            "django.middleware.security.SecurityMiddleware",
            "whitenoise.middleware.WhiteNoiseMiddleware",
            "django.contrib.sessions.middleware.SessionMiddleware",
            "corsheaders.middleware.CorsMiddleware",
            "django.middleware.common.CommonMiddleware",
            "debug_toolbar.middleware.DebugToolbarMiddleware",
            "django.middleware.csrf.CsrfViewMiddleware",
            "django.contrib.auth.middleware.AuthenticationMiddleware",
            "django.contrib.messages.middleware.MessageMiddleware",
            "django.middleware.clickjacking.XFrameOptionsMiddleware",
            "django.middleware.cache.FetchFromCacheMiddleware",
            "django_prometheus.middleware.PrometheusAfterMiddleware",
        ],
        environ=False,
    )
    REST_FRAMEWORK = values.DictValue(
        {
            "DEFAULT_PERMISSION_CLASSES": [
                "rest_framework.permissions.DjangoModelPermissionsOrAnonReadOnly"
            ],
            "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
            "PAGE_SIZE": 10,
            "DEFAULT_RENDERER_CLASSES": [
                "rest_framework.renderers.JSONRenderer",
                "rest_framework.renderers.BrowsableAPIRenderer",
            ],
            "DEFAULT_AUTHENTICATION_CLASSES": (
                "rest_framework.authentication.TokenAuthentication",
            ),
            # "DEFAULT_THROTTLE_CLASSES": [
            #     "rest_framework.throttling.AnonRateThrottle",
            # ],
            "DEFAULT_THROTTLE_RATES": {"anon": "1/minute", "user": "6/minute"},
            "DEFAULT_PARSER_CLASSES": [
                "rest_framework.parsers.JSONParser",
            ],
            "DEFAULT_FILTER_BACKENDS": [
                "django_filters.rest_framework.DjangoFilterBackend",
            ],
            "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
        },
        environ=False,
    )

    logger.add(
        Base.DEBUG_LOG_FILE,
        format=Base.LOG_FORMAT,
        diagnose=True,
        catch=True,
        backtrace=True,
        level="DEBUG",
    )

    logger.add(
        Base.DEFAULT_HANDLER,
        format=Base.LOG_FORMAT,
        diagnose=True,
        catch=True,
        backtrace=False,
        level="DEBUG",
    )


class Development(Base):
    INTERNAL_IPS = ["127.0.0.1"]
    ALLOWED_HOSTS = values.ListValue(["*", "localhost"], environ=False)
    CORS_ALLOW_ALL_ORIGINS = values.BooleanValue(True, environ=False)
    CSRF_TRUSTED_ORIGINS = ["https://*", "http://*"]
    DEBUG = values.BooleanValue(True, environ=False)
    INSTALLED_APPS = values.ListValue(
        [
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
            "rest_framework.authtoken",
            "django_filters",
            "corsheaders",
            "debug_toolbar",
            "storages",
            "djoser",
            "graphene_django",
            "crispy_forms",
            "crispy_bootstrap5",
            "django_prometheus",
            "drf_spectacular",
            "django_select2",
            # Project Apps
            "applications.API",
            "applications.graphQL",
            "drf_spectacular_sidecar",
        ],
        environ=False,
    )

    MIDDLEWARE = values.ListValue(
        [
            "django_prometheus.middleware.PrometheusBeforeMiddleware",
            "django.middleware.cache.UpdateCacheMiddleware",
            "django.middleware.security.SecurityMiddleware",
            "whitenoise.middleware.WhiteNoiseMiddleware",
            "django.contrib.sessions.middleware.SessionMiddleware",
            "corsheaders.middleware.CorsMiddleware",
            "django.middleware.common.CommonMiddleware",
            "debug_toolbar.middleware.DebugToolbarMiddleware",
            "django.middleware.csrf.CsrfViewMiddleware",
            "django.contrib.auth.middleware.AuthenticationMiddleware",
            "django.contrib.messages.middleware.MessageMiddleware",
            "django.middleware.clickjacking.XFrameOptionsMiddleware",
            "django.middleware.cache.FetchFromCacheMiddleware",
            "django_prometheus.middleware.PrometheusAfterMiddleware",
        ],
        environ=False,
    )

    #!SECTION End - Database and Caching

    # SECTION Start - DRF Settings
    REST_FRAMEWORK = values.DictValue(
        {
            "DEFAULT_PERMISSION_CLASSES": [
                "rest_framework.permissions.DjangoModelPermissionsOrAnonReadOnly"
            ],
            "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
            "PAGE_SIZE": 10,
            "DEFAULT_RENDERER_CLASSES": [
                "rest_framework.renderers.JSONRenderer",
                "rest_framework.renderers.BrowsableAPIRenderer",
            ],
            "DEFAULT_AUTHENTICATION_CLASSES": (
                "rest_framework.authentication.TokenAuthentication",
            ),
            # "DEFAULT_THROTTLE_CLASSES": [
            #     "rest_framework.throttling.AnonRateThrottle",
            # ],
            "DEFAULT_THROTTLE_RATES": {"anon": "1/minute", "user": "6/minute"},
            "DEFAULT_PARSER_CLASSES": [
                "rest_framework.parsers.JSONParser",
            ],
            "DEFAULT_FILTER_BACKENDS": [
                "django_filters.rest_framework.DjangoFilterBackend",
            ],
            "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
        },
        environ=False,
    )
    #!SECTION End - DRF Settings

    # SECTION Start - Logging
    logger.add(
        Base.DEBUG_LOG_FILE,
        format=Base.LOG_FORMAT,
        diagnose=True,
        catch=True,
        backtrace=True,
        level="DEBUG",
    )

    logger.add(
        Base.DEFAULT_HANDLER,
        format=Base.LOG_FORMAT,
        diagnose=True,
        catch=True,
        backtrace=False,
        level="DEBUG",
    )


# SECTION End - Logging
