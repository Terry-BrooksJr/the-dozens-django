"""
module: core.settings

Django settings for thedozens project.

"""

import json
import os
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import TextIO

from configurations import Configuration, values
from ghapi.all import GhApi
from loguru import logger


# --- drf-spectacular postprocessing hook to inject TokenAuth without using APPEND_COMPONENTS ---
def add_token_auth_scheme(result, generator, request, public):
    try:
        components = result.setdefault("components", {})
        security_schemes = components.setdefault("securitySchemes", {})
        security_schemes["TokenAuth"] = {
            "type": "apiKey",
            "in": "header",
            "name": "Authorization",
            "description": (
                "Token-based authentication. Supply your token like so:\n\n"
                "`Authorization: Token <your_token>`"
            ),
        }
    except Exception:  # keep schema generation resilient
        pass
    return result


# --- Safety: normalize APPEND_COMPONENTS in case an env var or override sets it as a string ---
def _normalize_append_components(settings_dict: dict) -> dict:
    ac = settings_dict.get("APPEND_COMPONENTS")
    if isinstance(ac, str):
        try:
            parsed = json.loads(ac)
            settings_dict["APPEND_COMPONENTS"] = (
                parsed if isinstance(parsed, dict) else {}
            )
        except Exception:
            settings_dict["APPEND_COMPONENTS"] = {}
    elif ac is None:
        settings_dict["APPEND_COMPONENTS"] = {}
    return settings_dict


def log_warning(
    message: str,
    category: type[Warning],
    filename: str,
    lineno: int,
    file: TextIO | None = None,
    line: str | None = None,
) -> None:
    file_info = f" [{getattr(file, 'name', '')}]" if file else ""
    line_info = f" | {line.strip()}" if line else ""
    logger.warning(
        f"{filename}:{lineno}{file_info} - {category.__name__}: {message}{line_info}"
    )


NSFW_WORD_LIST_URI = values.URLValue(
    environ=True, environ_prefix=None, environ_name="NSFW_WORD_LIST_URI"
)
GLOBAL_NOW = datetime.now(tz=timezone.utc)

BASE_DIR = values.PathValue(Path(__file__).resolve().parent.parent, environ=False)

IGNORED_INSULT_CATEGORIES = values.ListValue(["TEST", "X"], environ=False)
INSULT_REFERENCE_ID_PREFIX_OPTIONS = values.ListValue(
    ["GIGGLE", "CHUCKLE", "SNORT", "SNICKER", "CACKLE"], environ=False
)


class Base(Configuration):
    """
    Base configuration class for Django settings in the thedozens project.
    Provides core settings for application definition, logging, database, static files, authentication, and integrations.

    This class centralizes environment-based and default values for the Django project, including logging, database, static/media storage, REST API documentation, GraphQL, and email settings.
    It is intended to be subclassed for specific environments such as Production, Development, Offline, and Testing.
    """

    # SECTION Start - Application definition
    SECRET_KEY = values.SecretValue(
        environ=True, environ_prefix=None, environ_name="SECRET_KEY"
    )
    SITE_ID = values.PositiveIntegerValue(
        environ=True, environ_prefix=None, environ_name="SITE_ID"
    )
    GITHUB_API_OWNER = values.Value("terry-brooks-lrn", environ=False)
    GITHUB_API_REPO = values.Value("the-dozens-django", environ=False)
    GITHUB_API_TOKEN = values.SecretValue(
        environ=True,
        environ_prefix=None,
        environ_name="GITHUB_ACCESS_TOKEN",
    )
    _logger_configured = False

    @classmethod
    def get_github_api(cls) -> GhApi:
        return GhApi(
            owner=cls.GITHUB_API_OWNER,
            repo=cls.GITHUB_API_REPO,
            token=cls.GITHUB_API_TOKEN,
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
    # Silence RemovedInDjango60Warning — use assume_scheme on URLField when upgrading to Django 6.0
    FORMS_URLFIELD_ASSUME_HTTPS = True
    #!SECTION END - Application definition

    # SECTION Start - Media, Files and Static Assests Storage

    #!SECTION End - Media, Files and Static Assests Storage

    # SECTION Start- Logging
    LOG_FORMAT = "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <white>{message}</white>"
    DEFAULT_LOGGER_CONFIG = {
        "format": LOG_FORMAT,
        "diagnose": False,
        "catch": True,
        "backtrace": False,
        "serialize": False,
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
    for _p in (PRIMARY_LOG_FILE, CRITICAL_LOG_FILE, DEBUG_LOG_FILE):
        _p.parent.mkdir(parents=True, exist_ok=True)
    logger.remove()
    warnings.filterwarnings("default")
    warnings.showwarning = log_warning
    current_sinks = [
        PRIMARY_LOG_FILE,
        CRITICAL_LOG_FILE,
        DEBUG_LOG_FILE,
        DEFAULT_HANDLER,
    ]
    for sink in current_sinks:
        logger.add(sink, **DEFAULT_LOGGER_CONFIG)

    _default_logger_configured = True
    #!SECTION END - Logging

    # Track if logger has been configured to prevent duplicate handlers
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
                },
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
        os.path.join(BASE_DIR, "static"),  # pyrefly: ignore
    ]
    STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")
    template_dir = values.ListValue(
        [Path(os.path.join(BASE_DIR, "templates"))],  # pyrefly: ignore
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
        "TITLE": "Yo' Momma - The Joke API",
        "VERSION": "1.0.0",
        "SERVE_INCLUDE_SCHEMA": True,
        "OAS_VERSION": "3.0.3",
        "COMPONENT_SPLIT_REQUEST": True,
        "SECURITY": [{"TokenAuth": []}],
        "AUTHENTICATION_WHITELIST": [],
        "SERVE_AUTHENTICATION": None,
        "APPEND_COMPONENTS": {
            "schemas": {
                "ErrorResponse": {
                    "type": "object",
                    "properties": {
                        "detail": {
                            "type": "string",
                            "description": "Human-readable error message",
                        },
                        "code": {
                            "type": "string",
                            "description": "Machine-readable error code",
                        },
                        "status_code": {
                            "type": "integer",
                            "description": "HTTP status code",
                        },
                    },
                    "required": ["detail", "code", "status_code"],
                },
                "ValidationErrorResponse": {
                    "type": "object",
                    "properties": {
                        "detail": {
                            "type": "string",
                            "description": "Human-readable error message",
                        },
                        "code": {
                            "type": "string",
                            "description": "Machine-readable error code",
                        },
                        "status_code": {
                            "type": "integer",
                            "description": "HTTP status code",
                        },
                        "errors": {
                            "type": "object",
                            "description": "Field-specific validation errors",
                            "additionalProperties": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                        },
                    },
                    "required": ["detail", "code", "status_code", "errors"],
                },
            },
            "responses": {
                "401": {
                    "description": "Authentication credentials required",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                            "examples": {
                                "authentication_required": {
                                    "summary": "Missing or invalid authentication credentials",
                                    "description": "This endpoint requires valid authentication. Provide a valid token in the Authorization header.",
                                    "value": {
                                        "detail": "Yo momma so unknown, the server said 'New phone, who this?'",
                                        "code": "authentication_failed",
                                        "status_code": 401,
                                    },
                                }
                            },
                        }
                    },
                },
                "403": {
                    "description": "Insufficient permissions to access this resource",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                            "examples": {
                                "permission_denied": {
                                    "summary": "User lacks required permissions",
                                    "description": "The authenticated user does not have permission to perform this action on the requested resource.",
                                    "value": {
                                        "detail": "Yo momma so restricted, even admin don't have clearance.",
                                        "code": "permission_denied",
                                        "status_code": 403,
                                    },
                                },
                                "owner_only_access": {
                                    "summary": "Only resource owner can modify",
                                    "description": "This resource can only be modified by its owner. You can only modify insults that you created.",
                                    "value": {
                                        "detail": "You can only modify resources that you own.",
                                        "code": "permission_denied",
                                        "status_code": 403,
                                    },
                                },
                            },
                        }
                    },
                },
                "404": {
                    "description": "The requested resource could not be found",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                            "examples": {
                                "resource_not_found": {
                                    "summary": "Requested resource does not exist",
                                    "description": "The resource with the specified identifier was not found or may have been removed.",
                                    "value": {
                                        "detail": "Yo momma so lost, she tried to route to this page with Apple Maps.",
                                        "code": "not_found",
                                        "status_code": 404,
                                    },
                                },
                                "insult_not_found": {
                                    "summary": "Insult with specified ID does not exist",
                                    "description": "The insult with the provided reference_id was not found in our database.",
                                    "value": {
                                        "detail": "Insult not found.",
                                        "code": "not_found",
                                        "status_code": 404,
                                    },
                                },
                                "category_not_found": {
                                    "summary": "Category with specified key/name does not exist",
                                    "description": "The category with the provided key or name was not found. Check available categories using the /api/categories endpoint.",
                                    "value": {
                                        "detail": "Category not found.",
                                        "code": "not_found",
                                        "status_code": 404,
                                    },
                                },
                                "no_results_found": {
                                    "summary": "No resources match the specified filters",
                                    "description": "No resources were found that match your search criteria. Try adjusting your filters or search parameters.",
                                    "value": {
                                        "detail": "No results found matching the provided criteria.",
                                        "code": "not_found",
                                        "status_code": 404,
                                    },
                                },
                            },
                        }
                    },
                },
                "429": {
                    "description": "API rate limit exceeded",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                            "examples": {
                                "rate_limit_exceeded": {
                                    "summary": "Too many requests in given time period",
                                    "description": "You have exceeded the API rate limit. Please wait before making additional requests.",
                                    "value": {
                                        "detail": "Request was throttled. Expected available in 60 seconds.",
                                        "code": "throttled",
                                        "status_code": 429,
                                    },
                                }
                            },
                        }
                    },
                },
                "500": {
                    "description": "Internal server error occurred",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                            "examples": {
                                "internal_server_error": {
                                    "summary": "Unexpected server error",
                                    "description": "An unexpected error occurred on the server. Please try again later or contact support if the problem persists.",
                                    "value": {
                                        "detail": "Yo momma broke the server just by showing up.",
                                        "code": "server_error",
                                        "status_code": 500,
                                    },
                                }
                            },
                        }
                    },
                },
            },
        },
        "POSTPROCESSING_HOOKS": ["core.settings.add_token_auth_scheme"],
        "SWAGGER_UI_SETTINGS": {
            "deepLinking": True,
            "persistAuthorization": True,
            "displayOperationId": False,
            "tryItOutEnabled": True,
            "requestSnippetsEnabled": False,
            "syntaxHighlight.theme": "arta",
        },
        "SWAGGER_UI_DIST": "https://cdn.jsdelivr.net/npm/swagger-ui-dist@latest",
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
    MAILER_EMAIL_BACKEND = values.Value("mailer.backend.DbBackend", environ=False)
    EMAIL_BACKEND = MAILER_EMAIL_BACKEND
    EMAIL_HOST = values.Value(
        environ=True, environ_prefix=None, environ_name="EMAIL_SERVER"
    )
    EMAIL_PORT = values.PositiveIntegerValue(
        environ=True, environ_prefix=None, environ_name="EMAIL_SSL_PORT"
    )
    EMAIL_USE_TLS = False
    EMAIL_HOST_USER = values.Value(
        environ=True, environ_prefix=None, environ_name="NOTIFICATION_SENDER_EMAIL"
    )
    EMAIL_HOST_PASSWORD = values.SecretValue(
        environ=True, environ_prefix=None, environ_name="EMAIL_ACCT_PASSWORD"
    )
    DEFAULT_FROM_EMAIL = EMAIL_HOST_USER

    CACHES = values.DictValue(
        {
            "default": {
                "BACKEND": "django_prometheus.cache.backends.redis.RedisCache",
                "LOCATION": os.environ["REDIS_CACHE_TOKEN"],
                "OPTIONS": {
                    "CLIENT_CLASS": "django_redis.client.DefaultClient",
                    "SOCKET_CONNECT_TIMEOUT": 0.5,
                    "SOCKET_TIMEOUT": 0.5,
                    "RETRY_ON_TIMEOUT": False,
                    "PARSER_CLASS": "redis.connection._HiredisParser",
                    "CONNECTION_POOL_KWARGS": {
                        "max_connections": 10  # Example: Limit the pool to 10 connections
                    },
                },
                "TIMEOUT": 300,
            },
            "select2": {
                "BACKEND": "django_prometheus.cache.backends.redis.RedisCache",
                "LOCATION": f"{os.environ['REDIS_CACHE_TOKEN']}/2",
                "OPTIONS": {
                    "CLIENT_CLASS": "django_redis.client.DefaultClient",
                    "SOCKET_CONNECT_TIMEOUT": 0.5,
                    "SOCKET_TIMEOUT": 0.5,
                    "RETRY_ON_TIMEOUT": False,
                    "PARSER_CLASS": "redis.connection._HiredisParser",
                    "CONNECTION_POOL_KWARGS": {
                        "max_connections": 5  # Example: Limit the pool to 10 connections
                    },
                },
                "TIMEOUT": 300,
            },
        }
    )
    SELECT2_CACHE_BACKEND = "select2"

    EMAIL_HOST = values.Value(
        environ=True, environ_prefix=None, environ_name="EMAIL_SERVER"
    )
    EMAIL_USE_TLS = values.BooleanValue(True, environ=False)
    EMAIL_TIMEOUT = 30
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
            "mailer",
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
            "django.middleware.csrf.CsrfViewMiddleware",
            "django.contrib.auth.middleware.AuthenticationMiddleware",
            "django.contrib.messages.middleware.MessageMiddleware",
            "django.middleware.clickjacking.XFrameOptionsMiddleware",
            "django.middleware.cache.FetchFromCacheMiddleware",
            "django_prometheus.middleware.PrometheusAfterMiddleware",
        ],
        environ=False,
    )
    DEBUG = values.BooleanValue(False, environ=False)
    CSRF_TRUSTED_ORIGINS = values.ListValue(
        environ=True, environ_prefix=None, environ_name="ALLOWED_ORIGINS"
    )
    CORS_ALLOWED_ORIGINS = json.loads(os.environ.get("ALLOWED_ORIGINS", "[]"))
    # SECTION Start - Production Database

    #!SECTION End - Database and Caching
    # SECTION Start - DRF Settings
    REST_FRAMEWORK = values.DictValue(
        {
            "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
            "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
            "PAGE_SIZE": 10,
            "DEFAULT_RENDERER_CLASSES": [
                "rest_framework.renderers.JSONRenderer",
                "rest_framework.renderers.BrowsableAPIRenderer",
            ],
            "DEFAULT_AUTHENTICATION_CLASSES": (
                "applications.API.authentication.FlexibleTokenAuthentication",
            ),
            "EXCEPTION_HANDLER": "applications.API.errors.yo_momma_exception_handler",
            "DEFAULT_THROTTLE_CLASSES": [
                "rest_framework.throttling.AnonRateThrottle",
            ],
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

    if Base._logger_configured:
        logger.remove()
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
        Base._logger_configured = True


class Offline(Base):
    INTERNAL_IPS = ["*"]
    ALLOWED_HOSTS = ["*"]
    DEBUG = True
    CORS_ALLOW_ALL_ORIGINS = True
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
                "applications.API.authentication.FlexibleTokenAuthentication",
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

    # Single combined handler for console output with file rotation for debug logs
    if not Base._logger_configured:
        logger.add(
            Base.DEFAULT_HANDLER,
            format=Base.LOG_FORMAT,
            diagnose=True,
            catch=True,
            backtrace=False,
            level="DEBUG",
        )
        Base._logger_configured = True


class Development(Base):
    INTERNAL_IPS = ["127.0.0.1"]
    ALLOWED_HOSTS = values.ListValue(["*", "localhost"], environ=False)
    CORS_ALLOW_ALL_ORIGINS = values.BooleanValue(True, environ=False)
    CSRF_TRUSTED_ORIGINS = ["https://*", "http://*"]
    DEBUG = True
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
            "mailer",
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
                "applications.API.authentication.FlexibleTokenAuthentication",
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
    # Single combined handler for console output
    # Force logger configuration for Development environment
    if not Base._logger_configured:
        logger.remove()
        logger.add(
            Base.DEFAULT_HANDLER,
            format=Base.LOG_FORMAT,
            diagnose=True,
            catch=True,
            backtrace=False,
            level="DEBUG",
        )
        Base._logger_configured = True


class Testing(Development):
    DATABASES = values.DictValue(
        {
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": os.path.join(str(BASE_DIR), "test_db.sqlite3"),
            }
        },
        environ=False,
    )


# Configure logger for Testing environment
# Must be done at module level AFTER class definition
# Disable loguru's diagnostic features to avoid conflicts with coverage tracing
if os.getenv("DJANGO_CONFIGURATION") == "Testing" and not Base._logger_configured:
    logger.remove()
    logger.add(
        Base.DEFAULT_HANDLER,
        format=Base.LOG_FORMAT,
        level="WARNING",
        diagnose=False,
        catch=False,
        backtrace=False,
    )
    Base._logger_configured = True


# --- Coerce APPEND_COMPONENTS for all configurations ---
for _cfg in (Base, Production, Development, Offline, Testing):
    _cfg.SPECTACULAR_SETTINGS = _normalize_append_components(
        dict(_cfg.SPECTACULAR_SETTINGS)
    )
