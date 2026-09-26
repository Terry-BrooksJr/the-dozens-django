# -*- coding: utf-8 -*-
"""
module: core.settings

Django settings for thedozens project.

"""

import logging
import os
import sys
import threading
import time
import warnings
from datetime import datetime, timezone
from pathlib import Path

from configurations import Configuration, values
from github import Github
from loguru import logger
from loki_logger_handler.loki_logger_handler import LokiLoggerHandler

from applications.ld_integration.client import configure_launchdarkly
from common.helpers import (
    SanitizingLoguruFormatter,
    _force_utc_time,
    _insert_after_middleware,
    _normalize_append_components,
    ld_loguru_sink,
    log_warning,
)

GLOBAL_NOW = datetime.now(tz=timezone.utc)

BASE_DIR = values.PathValue(Path(__file__).resolve().parent.parent, environ=False)

IGNORED_INSULT_CATEGORIES = values.ListValue(["TEST", "X"], environ=False)
INSULT_REFERENCE_ID_PREFIX_OPTIONS = values.ListValue(
    ["GIGGLE", "CHUCKLE", "SNORT", "SNICKER", "CACKLE"], environ=False
)


# ---------------------------------------------------------------------------
# Shared configuration building blocks
# ---------------------------------------------------------------------------
# Plain lists/dicts that configuration classes compose via spread/concat so
# each environment only declares its *differences* from the baseline.

_INSTALLED_APPS_CORE = [
    # 0) Instrumentation that wants to wrap others early
    # ld_integration must be first: its AppConfig.ready() configures the
    # LaunchDarkly client and observability plugin, which patch httpx/anthropic
    # globally. Any app that makes those calls during its own ready() before
    # this runs gets its early spans silently dropped ("observability singleton
    # used before it was initialized").
    "applications.ld_integration",
    "jazzmin",
    "django_prometheus",
    # 1) Django built-ins
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.sites",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # 2) DRF UI skin — must come BEFORE rest_framework
    "rest_wind",
    # 3) Core framework add-ons
    "rest_framework",
    "rest_framework.authtoken",
    "django_filters",
    # 4) Third-party apps
    "corsheaders",
    "storages",
    "mailer",
    "djoser",
    "graphene_django",
    "crispy_forms",
    "crispy_bootstrap5",
    # 5) API schema tooling (after DRF)
    "drf_spectacular",
    "drf_spectacular_sidecar",
]

_INSTALLED_APPS_PROJECT = [
    "applications.API",
    "applications.graphQL",
]

_MIDDLEWARE_CORE = [
    "django_prometheus.middleware.PrometheusBeforeMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.cache.UpdateCacheMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django.middleware.cache.FetchFromCacheMiddleware",
    "django_prometheus.middleware.PrometheusAfterMiddleware",
    "common.middleware.RequestIDMiddleware",
]


_MIDDLEWARE_WITH_DEBUG = _insert_after_middleware(
    _MIDDLEWARE_CORE,
    "django.middleware.common.CommonMiddleware",
    "debug_toolbar.middleware.DebugToolbarMiddleware",
)

_REST_FRAMEWORK_COMMON = {
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 10,
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ],
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "applications.API.authentication.FlexibleTokenAuthentication",
    ),
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

_REST_FRAMEWORK_DEV = {
    **_REST_FRAMEWORK_COMMON,
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.DjangoModelPermissionsOrAnonReadOnly"
    ],
    "DEFAULT_THROTTLE_RATES": {"anon": "1/minute", "user": "6/minute"},
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
    ],
}

_LOCAL_STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}


class Base(Configuration):
    """
    Base configuration class for Django settings in the thedozens project.
    Provides core settings for application definition, logging, database, static files, authentication, and integrations.

    This class centralizes environment-based and default values for the Django project, including logging, database, static/media storage, REST API documentation, GraphQL, and email settings.
    It is intended to be subclassed for specific environments such as Production, Development, Offline, and Staging.
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

    @classmethod
    def get_github_api(cls):
        """Return a PyGithub `Repository` handle for this project's GitHub repo.

        Authenticates with `GITHUB_API_TOKEN` and looks up
        `GITHUB_API_OWNER/GITHUB_API_REPO`.

        Returns:
            github.Repository.Repository: The repo object for further API calls.
        """
        g = Github(cls.GITHUB_API_TOKEN)
        return g.get_repo(f"{cls.GITHUB_API_OWNER}/{cls.GITHUB_API_REPO}")

    ROOT_URLCONF = values.Value("core.urls", environ=False)
    WSGI_APPLICATION = values.Value("core.wsgi.application", environ=False)

    ADMINS = values.ListValue(["Terry@BrooksJr.com"], environ=False)
    LANGUAGE_CODE = values.Value("en-us", environ=False)
    APPEND_SLASH = values.BooleanValue(True, environ=False)
    VIEW_CACHE_TTL = values.PositiveIntegerValue(
        environ=True, environ_prefix=None, environ_name="CACHE_TTL"
    )

    LAUNCHDARKLY_SDK_KEY = os.getenv("LAUNCHDARKLY_SDK_KEY")
    LAUNCHDARKLY_ENABLED = os.getenv("LAUNCHDARKLY_ENABLED", "false").lower() == "true"
    LAUNCHDARKLY_OBSERVABILITY_ENABLED = os.getenv(
        "LAUNCHDARKLY_OBSERVABILITY_ENABLED", ""
    ).lower() in ("1", "true", "yes", "on")
    LAUNCHDARKLY_SERVICE_NAME = os.getenv("LAUNCHDARKLY_SERVICE_NAME")
    configure_launchdarkly(
        sdk_key=LAUNCHDARKLY_SDK_KEY,
        enabled=LAUNCHDARKLY_ENABLED,
        obs_enabled=LAUNCHDARKLY_OBSERVABILITY_ENABLED,
        service_name=LAUNCHDARKLY_SERVICE_NAME or "django-service",
        service_version=os.getenv("LAUNCHDARKLY_SERVICE_VERSION", "dev"),
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
    # Timestamps are forced to UTC (see _force_utc_time patcher and the
    # logging.Formatter.converter override below) regardless of TIME_ZONE, so
    # log lines from different hosts/containers stay directly comparable.
    LOG_FORMAT = "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}Z</green> | {level.icon}  <level><bold> {level: <8}</bold></level> |<blue>{message}</blue>"

    DEFAULT_LOGGER_CONFIG = {
        "format": LOG_FORMAT,
        "diagnose": False,
        "catch": True,
        "backtrace": False,
        "serialize": False,
    }
    # File sinks get daily rotation and a 30-day rolling window.
    # Rotated files are gzip-compressed to keep the logs/ dir manageable.
    # stdout / remote sinks (LD) do not support these parameters and use
    # DEFAULT_LOGGER_CONFIG as-is.
    FILE_LOGGER_CONFIG = {
        **DEFAULT_LOGGER_CONFIG,
        "rotation": "00:00",  # rotate at midnight every day
        "retention": "30 days",  # delete rotated files older than 30 days
        "compression": "gz",  # compress rotated files
    }
    LOG_FILE_DIR = os.getenv("LOG_FILE_DIRECTORY", "logs")
    PRIMARY_LOG_FILE = Path(
        os.path.join(BASE_DIR, LOG_FILE_DIR, "primary_ops.log")
    )  # pyrefly: ignore
    CRITICAL_LOG_FILE = Path(
        os.path.join(BASE_DIR, LOG_FILE_DIR, "fatal.log")
    )  # pyrefly: ignore
    DEBUG_LOG_FILE = Path(
        os.path.join(BASE_DIR, LOG_FILE_DIR, "utility.log")
    )  # pyrefly: ignore
    DEBUG_PROPAGATE_EXCEPTIONS = True
    DEFAULT_HANDLER = sys.stdout

    # Guards configure_logging_common() so it runs exactly once per process
    # no matter how many times post_setup() fires (autoreload, test runner).
    _logging_configured = False
    _logging_lock = threading.Lock()

    @classmethod
    def is_logging_configured(cls) -> bool:
        """Whether `configure_logging_common()` has already run in this process."""
        return Base._logging_configured

    @classmethod
    def set_logging_configured_state(cls, value: bool) -> None:
        """Force the shared, process-wide logging guard to a specific state.

        Public accessor for the `_logging_configured` flag, for test
        setup/teardown that needs to simulate an already-configured process
        or reset the guard between tests.
        """
        Base._logging_configured = bool(value)

    @classmethod
    def configure_logging_common(cls) -> bool:
        """Process-wide logging setup shared by every environment.

        Runs once via post_setup() (see below), which django-configurations
        calls only on the concrete class DJANGO_CONFIGURATION selects — unlike
        the previous implementation, this no longer runs once per Base
        subclass *defined* in this module (Production/Offline/Development/
        Staging all executed unconditionally at import time, in file order,
        each stomping on whatever logging setup the previous one made,
        regardless of which environment was actually active).

        Returns:
            True if this call performed setup (first caller this process).
            False if logging was already configured (subclasses should skip
            adding their own sinks too).
        """
        # Always use the state owned by Base.  Subclasses may override or
        # inherit these attributes, but logging configuration is process-wide.
        with Base._logging_lock:
            # Keep the guard on Base itself: assigning through ``cls`` would
            # create a separate flag on whichever environment subclass ran
            # first.
            if Base._logging_configured:
                return False

            for log_file in (
                cls.PRIMARY_LOG_FILE,
                cls.CRITICAL_LOG_FILE,
                cls.DEBUG_LOG_FILE,
            ):
                log_file.parent.mkdir(parents=True, exist_ok=True)

            logger.remove()
            warnings.filterwarnings("default")
            warnings.showwarning = log_warning

            # Make every stdlib logging.Formatter (ours, gunicorn's, Django's)
            # render timestamps in UTC instead of TIME_ZONE/server-local time.
            logging.Formatter.converter = time.gmtime
            # Same for Loguru, which otherwise stamps records with local time.
            logger.configure(patcher=_force_utc_time)

            logging.getLogger("opentelemetry.attributes").setLevel(logging.ERROR)
            Base._logging_configured = True
            return Base._logging_configured

    @classmethod
    def configure_logging(cls):
        """Default sinks: rotating log files + stdout (+ optional LD sink).

        Concrete environments (Offline, Development, Production, Staging)
        override this with their own sinks; this only applies if Base is
        ever configured directly.
        """
        if not cls.configure_logging_common():
            return

        # File sinks: rotate daily, retain 30 days, compress rotated files.
        for file_sink in (
            cls.PRIMARY_LOG_FILE,
            cls.CRITICAL_LOG_FILE,
            cls.DEBUG_LOG_FILE,
        ):
            logger.add(file_sink, **cls.FILE_LOGGER_CONFIG)

        # Non-file sinks: no rotation/retention parameters.
        stream_sinks = [cls.DEFAULT_HANDLER]
        if cls.LAUNCHDARKLY_OBSERVABILITY_ENABLED:
            stream_sinks.append(ld_loguru_sink)
        for sink in stream_sinks:
            logger.add(sink, **cls.DEFAULT_LOGGER_CONFIG)

    @classmethod
    def post_setup(cls):
        """django-configurations lifecycle hook: runs once Value()s resolve,
        only on the selected configuration class — the explicit place for
        logging init instead of side effects in class bodies at import time.
        """
        super().post_setup()
        cls.configure_logging()

    #!SECTION END - Logging

    INSTALLED_APPS = values.ListValue(
        _INSTALLED_APPS_CORE + _INSTALLED_APPS_PROJECT, environ=False
    )

    MIDDLEWARE = values.ListValue(_MIDDLEWARE_CORE, environ=False)

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
        environ=True, environ_prefix=None, environ_name="S3_OBJECT_STORAGE_KEY"
    )
    AWS_SECRET_ACCESS_KEY = values.SecretValue(
        environ=True, environ_prefix=None, environ_name="S3_OBJECT_STORAGE_SECRET"
    )
    AWS_STORAGE_BUCKET_NAME = values.SecretValue(
        environ=True, environ_prefix=None, environ_name="S3_OBJECT_STORAGE_BUCKET_NAME"
    )
    AWS_S3_ENDPOINT_URL = values.SecretValue(
        environ=True, environ_prefix=None, environ_name="S3_ENDPOINT_URL"
    )
    AWS_REGION_NAME = values.SecretValue(
        environ=True, environ_prefix=None, environ_name="S3_REGION_NAME"
    )
    AWS_QUERYSTRING_AUTH = False
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
            "BACKEND": "common.storage_backends.StaticStorage",
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
            "BACKEND": "common.storage_backends.MediaStorage",
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
                        "applications.ld_integration.context_processors.launchdarkly_user",
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
        "VERSION": os.getenv("API_VERSION", "1.0.0"),
        "SERVE_INCLUDE_SCHEMA": True,
        "OAS_VERSION": "3.0.3",
        # Cache the generated schema for 15 minutes — generation is expensive
        # (introspects every view/serializer on the fly) and the output is
        # deterministic until a deploy.  Without this, every ReDoc/Swagger page
        # load triggers a multi-second schema build before the UI can render.
        "SCHEMA_CACHE_TIMEOUT": 60 * 15,
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
        "POSTPROCESSING_HOOKS": ["common.helpers.add_token_auth_scheme"],
        "SWAGGER_UI_SETTINGS": {
            "deepLinking": True,
            "persistAuthorization": True,
            "displayOperationId": False,
            "tryItOutEnabled": True,
            "requestSnippetsEnabled": False,
            "syntaxHighlight.theme": "arta",
        },
        "SWAGGER_UI_DIST": "SIDECAR",
        "REDOC_DIST": "SIDECAR",
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

    # SECTION Start - Djoser Settings
    DJOSER = {
        "SEND_CONFIRMATION_EMAIL": True,
        "EMAIL": {
            "confirmation": "applications.API.emails.WelcomeEmail",
        },
        "EMAIL_FRONTEND_DOMAIN": "api.yo-momma.io",
        "EMAIL_FRONTEND_PROTOCOL": "https",
    }
    #!SECTION End - Djoser Settings

    #  SECTION Start - GraphQL Settings (Graphene-Django)
    GRAPHENE = values.DictValue(
        {
            "SCHEMA": "applications.graphQL.schema.schema",
            "MIDDLEWARE": [
                "graphene_django.debug.DjangoDebugMiddleware",
            ],
            # Show the Headers panel in the GraphiQL playground.
            "GRAPHIQL_HEADER_EDITOR_ENABLED": True,
            # Persist headers the developer enters across page reloads.
            "GRAPHIQL_SHOULD_PERSIST_HEADERS": True,
        },
        environ=False,
    )

    #!SECTION End - GraphQL Settings (Graphene-Django)

    # SECTION - Email Settings (Django-Mailer)
    # ImmediateDbBackend queues through django-mailer (for the MessageLog
    # audit trail) and drains the queue in the same call, since nothing in
    # this deploy schedules `manage.py send_mail` to do it later.
    EMAIL_BACKEND = "core.mailer_backends.ImmediateDbBackend"
    MAILER_EMAIL_BACKEND = values.Value(
        "django.core.mail.backends.smtp.EmailBackend", environ=False
    )
    # DB row locking (select_for_update) already prevents double-sends;
    # the file lock exists for long-running send_mail loops, which we don't use.
    MAILER_USE_FILE_LOCK = False
    USE_REDIS_CACHE = os.getenv("USE_REDIS_CACHE", "true").lower() == "true"

    if USE_REDIS_CACHE:
        CACHES = {
            "default": {
                "BACKEND": "django_prometheus.cache.backends.redis.RedisCache",
                "KEY_PREFIX": os.environ.get("CACHE_KEY_PREFIX", ""),
                "LOCATION": os.environ.get("REDIS_CACHE_TOKEN", ""),
                "OPTIONS": {
                    "CLIENT_CLASS": "django_redis.client.DefaultClient",
                    "CONNECTION_POOL_KWARGS": {
                        "max_connections": 100,
                        "retry_on_timeout": True,
                    },
                    "SOCKET_CONNECT_TIMEOUT": 2,
                    "SOCKET_TIMEOUT": 2,
                },
                "TIMEOUT": 600,
            }
        }
    else:
        CACHES = {
            "default": {
                "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                "LOCATION": "the-dozens-local",
            }
        }
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
    DEFAULT_FROM_EMAIL = EMAIL_HOST_USER
    MAILER_EMPTY_QUEUE_SLEEP = values.IntegerValue(
        environ=True, environ_prefix=None, environ_name="MAILER_EMPTY_QUEUE_SLEEP"
    )
    JAZZMIN_SETTINGS = {
        # title of the window (Will default to current_admin_site.site_title if absent or None)
        "site_title": "Yo Momma Jokes API",
        # Title on the login screen (19 chars max) (defaults to current_admin_site.site_header if absent or None)
        "site_header": "Yo Momma Jokes API",
        # Title on the brand (19 chars max) (defaults to current_admin_site.site_header if absent or None)
        "site_brand": "Yo Momma Jokes API",
        # Logo to use for your site, must be present in static files, used for brand on top left
        "site_logo": "https://cdn.jsdelivr.net/gh/Terry-BrooksJr/the-dozens-frontend@f74b735018f9e8d330f2d6e507eea05110f92905/assets/yo_momma_brand.png",
        # Logo to use for your site, must be present in static files, used for login form logo (defaults to site_logo)
        "login_logo": "https://cdn.jsdelivr.net/gh/Terry-BrooksJr/the-dozens-frontend@f74b735018f9e8d330f2d6e507eea05110f92905/assets/yo_momma_brand.png",
        # Logo to use for login form in dark themes (defaults to login_logo)
        "login_logo_dark": "https://cdn.jsdelivr.net/gh/Terry-BrooksJr/the-dozens-frontend@f74b735018f9e8d330f2d6e507eea05110f92905/assets/yo_momma_brand.png",
        # CSS classes that are applied to the logo above
        "site_logo_classes": "img-circle",
        # Relative path to a favicon for your site, will default to site_logo if absent (ideally 32x32 px)
        "site_icon": None,
        # Welcome text on the login screen
        "welcome_sign": "Welcome to the Yo Momma Jokes Backend",
        # Copyright on the footer
        "copyright": "Blackberry-Py Dev",
        # List of model admins to search from the search bar, search bar omitted if excluded
        # If you want to use a single search field you dont need to use a list, you can use a simple string
        "search_model": ["auth.User", "auth.Group"],
        # Field name on user model that contains avatar ImageField/URLField/Charfield or a callable that receives the user
        "user_avatar": None,
        ############
        # Top Menu #
        ############
        # Links to put along the top menu
        "topmenu_links": [
            # Url that gets reversed (Permissions can be added)
            {"name": "Home", "url": "admin:index", "permissions": ["auth.view_user"]},
            # external url that opens in a new window (Permissions can be added)
            {
                "name": "Support",
                "url": "https://github.com/terry-brooksjr/the-dozens-django/issues",
                "new_window": True,
            },
            # model admin to link to (Permissions checked against model)
            {"model": "auth.User"},
            # App with dropdown menu to all its models pages (Permissions checked against models)
            {"name": "Observability", "url": "/admin/observability/"},
        ],
        #############
        # User Menu #
        #############
        # Additional links to include in the user menu on the top right ("app" url type is not allowed)
        "usermenu_links": [
            {
                "name": "Support",
                "url": "https://github.com/terry-brooksjr/the-dozens-django/issues",
                "new_window": True,
            },
            {"model": "auth.user"},
        ],
        #############
        # Side Menu #
        #############
        # Whether to display the side menu
        "show_sidebar": True,
        # Whether to aut expand the menu
        "navigation_expanded": True,
        # Hide these apps when generating side menu e.g (auth)
        "hide_apps": ["sites"],
        # Hide these models when generating side menu (e.g auth.user)
        "hide_models": [],
        # List of apps (and/or models) to base side menu ordering off of (does not need to contain all apps/models)
        "order_with_respect_to": ["auth"],
        # Custom icons for side menu apps/models See https://fontawesome.com/icons?d=gallery&m=free&v=5.0.0,5.0.1,5.0.10,5.0.11,5.0.12,5.0.13,5.0.2,5.0.3,5.0.4,5.0.5,5.0.6,5.0.7,5.0.8,5.0.9,5.1.0,5.1.1,5.2.0,5.3.0,5.3.1,5.4.0,5.4.1,5.4.2,5.13.0,5.12.0,5.11.2,5.11.1,5.10.0,5.9.0,5.8.2,5.8.1,5.7.2,5.7.1,5.7.0,5.6.3,5.5.0,5.4.2
        # for the full list of 5.13.0 free icon classes
        "icons": {
            "auth": "fas fa-users-cog",
            "auth.user": "fas fa-user",
            "auth.Group": "fas fa-users",
            "applications.API.Insult": "fas fa-users",
            "applications.API.JokeReview": "fa-regular fa-file-circle-check",
        },
        # Icons that are used when one is not manually specified
        "default_icon_parents": "fas fa-chevron-circle-right",
        "default_icon_children": "fas fa-circle",
        #################
        # Related Modal #
        #################
        # Use modals instead of popups
        "related_modal_active": False,
        #############
        # UI Tweaks #
        #############
        # Relative paths to custom CSS/JS scripts (must be present in static files)
        "custom_css": None,
        "custom_js": None,
        # Whether to link font from fonts.googleapis.com (use custom_css to supply font otherwise)
        "use_google_fonts_cdn": True,
        # Whether to show the UI customizer on the sidebar
        "show_ui_builder": False,
        ###############
        # Change view #
        ###############
        # Render out the change view as a single form, or in tabs, current options are
        # - single
        # - horizontal_tabs (default)
        # - vertical_tabs
        # - collapsible
        # - carousel
        "changeform_format": "horizontal_tabs",
        # override change forms on a per modeladmin basis
        "changeform_format_overrides": {
            "auth.user": "collapsible",
            "auth.group": "vertical_tabs",
        },
        # Add a language dropdown into the admin
        "language_chooser": False,
    }


class Production(Base):
    """Production environment configuration.

    Locks down DEBUG, trusts the Traefik reverse proxy for scheme/host
    detection, and configures logging for stdout plus optional Loki and
    LaunchDarkly Observability sinks (see `configure_logging`).
    """

    ALLOWED_HOSTS = values.ListValue(
        environ=True, environ_prefix=None, environ_name="ALLOWED_HOSTS"
    )
    # Secret token that Prometheus must send as "Authorization: Bearer <token>"
    # when scraping /metrics.  Set METRICS_SCRAPE_TOKEN in Doppler.
    # IP-based allowlists are no longer used — Docker NAT makes them unreliable.
    METRICS_SCRAPE_TOKEN = values.Value(
        "",
        environ=True,
        environ_prefix=None,
        environ_name="METRICS_SCRAPE_TOKEN",
    )
    DEBUG = values.BooleanValue(False, environ=False)

    # ------------------------------------------------------------------ #
    # Reverse-proxy trust (Traefik)                                        #
    # ------------------------------------------------------------------ #
    # Traefik terminates TLS and forwards requests as HTTP to gunicorn.
    # Without these two settings Django reconstructs the wrong scheme:
    #   browser sends   Origin: https://yo-momma.io
    #   Django builds   http://yo-momma.io  (is_secure() == False)
    #   CSRF check      https:// != http://  → 403 on every admin POST
    #
    # SECURE_PROXY_SSL_HEADER tells Django to trust the X-Forwarded-Proto
    # header that Traefik adds, making request.is_secure() correct.
    # USE_X_FORWARDED_HOST makes request.get_host() use X-Forwarded-Host
    # so the origin comparison uses the public hostname, not the internal one.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    USE_X_FORWARDED_HOST = True

    # CSRF_TRUSTED_ORIGINS is read from the ALLOWED_ORIGINS Doppler secret.
    # Must include every public origin that can POST to Django, e.g.:
    #   ALLOWED_ORIGINS=["https://yo-momma.io","https://www.yo-momma.io"]
    # Provide a safe non-empty default so startup doesn't silently break when
    # the env var is absent — admin will still 403 without it, but at least
    # the error message is clear.
    CSRF_TRUSTED_ORIGINS = values.ListValue(
        default=[
            "https://yo-momma.io",
            "https://www.yo-momma.io",
            "https://dozens.nyc3.cdn.digitaloceanspaces.com",
        ],
        environ=True,
        environ_prefix=None,
        environ_name="ALLOWED_ORIGINS",
    )

    CORS_ALLOW_ALL_ORIGINS = True

    # SECTION Start - GraphQL Settings (Production overrides)
    # Remove DjangoDebugMiddleware in production — it leaks SQL query details in responses.
    GRAPHENE = values.DictValue(
        {
            "SCHEMA": "applications.graphQL.schema.schema",
            "MIDDLEWARE": [],
            # Keep the playground headers panel available in production.
            "GRAPHIQL_HEADER_EDITOR_ENABLED": True,
            # Persist headers the developer enters across page reloads.
            "GRAPHIQL_SHOULD_PERSIST_HEADERS": True,
        },
        environ=False,
    )
    #!SECTION End - GraphQL Settings (Production overrides)

    REST_FRAMEWORK = values.DictValue(
        {
            **_REST_FRAMEWORK_COMMON,
            "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
            "EXCEPTION_HANDLER": "applications.API.errors.yo_momma_exception_handler",
            "DEFAULT_THROTTLE_CLASSES": [
                "rest_framework.throttling.AnonRateThrottle",
            ],
            "DEFAULT_THROTTLE_RATES": {"anon": "4/minute", "user": "12/minute"},
        },
        environ=False,
    )

    # SECTION Start - API Schema / Docs (Production overrides)
    # Use CDN-hosted assets instead of drf-spectacular-sidecar so Swagger UI and
    # ReDoc load without depending on a collectstatic run against DigitalOcean Spaces.
    #
    # IMPORTANT — pin to the EXACT version bundled by drf-spectacular-sidecar
    # (currently 2.5.2).  Using @latest caused a silent hang: in 2026 @latest
    # resolves to ReDoc 3.x, which dropped the Redoc.init() API that our
    # custom template uses.  Pinning to 2.x ensures CDN == sidecar == template.
    #
    # When upgrading drf-spectacular-sidecar, also bump this pin:
    #   grep -r "Version:" .venv/lib/*/site-packages/drf_spectacular_sidecar/static/**/redoc/**/*.LICENSE.txt
    SPECTACULAR_SETTINGS = {
        **Base.SPECTACULAR_SETTINGS,
        "SWAGGER_UI_DIST": "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5",
        "REDOC_DIST": "https://cdn.jsdelivr.net/npm/redoc@2.5.2",
    }
    #!SECTION End - API Schema / Docs (Production overrides)

    # SECTION Start - Logging
    LAUNCHDARKLY_SERVICE_VERSION = os.getenv("LAUNCHDARKLY_SERVICE_VERSION")

    @classmethod
    def configure_logging(cls):
        """Production: stdout (+ optional Loki, + optional LD sink). No file
        sinks inside the container.
        """
        if not cls.configure_logging_common():
            return

        # Loki Log Handler - May Replace OTEL in future iterations
        if loki_url := os.getenv("LOKI_URL"):
            if loki_password := os.getenv("LOKI_PASSWORD"):
                loki_handler = LokiLoggerHandler(
                    url=loki_url,
                    auth=("lokiadmin", loki_password),
                    labels={"application": "dozen_api", "environment": "Production"},
                    label_keys={},
                    timeout=10,
                    default_formatter=SanitizingLoguruFormatter(),
                )
                logger.add(loki_handler, serialize=True)

        # serialize=False: plain text to stdout for local `docker logs`
        # readability; Loki gets its own serialized sink above.
        logger.add(sys.stdout, **{**cls.DEFAULT_LOGGER_CONFIG, "serialize": False})

        if cls.LAUNCHDARKLY_OBSERVABILITY_ENABLED:
            logger.add(ld_loguru_sink, **cls.DEFAULT_LOGGER_CONFIG)


class Offline(Base):
    """Configuration for the local Docker Compose environment.

    Runs with DEBUG on, permissive ALLOWED_HOSTS/CORS/CSRF for reaching the
    container under any local hostname, and local filesystem storage instead
    of S3-backed storage.
    """

    INTERNAL_IPS = ["*"]
    ALLOWED_HOSTS = ["*"]
    DEBUG = True
    CORS_ALLOW_ALL_ORIGINS = True
    # Allow any origin in the local Docker environment so admin works regardless
    # of which hostname/port is used to reach the container.
    CSRF_TRUSTED_ORIGINS = ["http://localhost:8000", "http://127.0.0.1:8000"]
    STATIC_URL = "/static/"
    STORAGES = _LOCAL_STORAGES
    INSTALLED_APPS = values.ListValue(
        _INSTALLED_APPS_CORE + ["debug_toolbar"] + _INSTALLED_APPS_PROJECT,
        environ=False,
    )
    MIDDLEWARE = values.ListValue(_MIDDLEWARE_WITH_DEBUG, environ=False)
    REST_FRAMEWORK = values.DictValue(_REST_FRAMEWORK_DEV, environ=False)

    @classmethod
    def configure_logging(cls):
        """Offline (local Docker): console only, verbose diagnostics."""
        if not cls.configure_logging_common():
            return
        logger.add(
            cls.DEFAULT_HANDLER,
            format=cls.LOG_FORMAT,
            diagnose=True,
            catch=True,
            backtrace=False,
            level="DEBUG",
        )


class Development(Base):
    """Configuration for running the project directly on a developer machine.

    Runs with DEBUG on, local dev CSRF/CORS origins, direct-SMTP email,
    local filesystem storage, Kolo profiling middleware, and console logging
    with an optional Loki sink when `LOKI_URL` is set.
    """

    INTERNAL_IPS = ["127.0.0.1"]
    ALLOWED_HOSTS = values.ListValue(["*", "localhost"], environ=False)
    CORS_ALLOW_ALL_ORIGINS = values.BooleanValue(True, environ=False)
    # Django's CSRF_TRUSTED_ORIGINS wildcard requires a base domain after the
    # "*" (e.g. "https://*.example.com" trusts subdomains of example.com); a
    # bare "https://*" has an empty subdomain pattern, which
    # django.utils.http.is_same_domain() rejects unconditionally — so this
    # was matching no origin at all. List the actual local dev origins instead.
    CSRF_TRUSTED_ORIGINS = ["http://localhost:8000", "http://127.0.0.1:8000"]
    DEBUG = True
    STATIC_URL = "/static/"
    WHITENOISE_AUTOREFRESH = True
    STORAGES = _LOCAL_STORAGES
    INSTALLED_APPS = values.ListValue(
        _INSTALLED_APPS_CORE + ["debug_toolbar"] + _INSTALLED_APPS_PROJECT,
        environ=False,
    )
    MIDDLEWARE = values.ListValue(
        ["kolo.middleware.KoloMiddleware"]
        + _insert_after_middleware(
            _MIDDLEWARE_WITH_DEBUG,
            "django_prometheus.middleware.PrometheusAfterMiddleware",
            "applications.ld_integration.middleware.LaunchDarklyContextMiddleware",
        ),
        environ=False,
    )
    REST_FRAMEWORK = values.DictValue(_REST_FRAMEWORK_DEV, environ=False)

    # SECTION Start - Logging
    @classmethod
    def configure_logging(cls):
        """Development: console output, plus Loki when LOKI_URL is set."""
        if not cls.configure_logging_common():
            return

        # Loki Log Handler - May Replace OTEL in future iterations
        if loki_url := os.getenv("LOKI_URL"):
            if loki_password := os.getenv("LOKI_PASSWORD"):
                loki_handler = LokiLoggerHandler(
                    url=loki_url,
                    auth=("lokiadmin", loki_password),
                    labels={"application": "dozen_api", "environment": "Development"},
                    label_keys={},
                    timeout=10,
                    default_formatter=SanitizingLoguruFormatter(),
                )
                logger.add(loki_handler, serialize=True)

        logger.add(
            cls.DEFAULT_HANDLER,
            format=cls.LOG_FORMAT,
            diagnose=True,
            catch=True,
            backtrace=False,
            level="DEBUG",
        )


class Staging(Development):
    """CI-only configuration used exclusively for GitHub Actions commit checks.

    Runs against Postgres rather than SQLite so tests exercise the same
    database engine used in production. The defaults below match the
    `postgres` service container defined in the `test` job of
    `.github/workflows/commit_check.yaml`, which sets these same
    PG_DATABASE_*/POSTGRES_DB values explicitly. They also let this
    configuration run locally (`task test:coverage`, `task run:test`,
    or bare pytest) against a local Postgres instance with the same
    credentials, without requiring every env var to be set by hand.
    """

    DATABASES = values.DictValue(
        {
            "default": {
                "ENGINE": "django.db.backends.postgresql",
                "NAME": os.getenv("POSTGRES_DB", "test_db"),
                "USER": os.getenv("PG_DATABASE_USER", "root"),
                "PASSWORD": os.getenv("PG_DATABASE_PASSWORD", "postgres"),
                "HOST": os.getenv("PG_DATABASE_HOST", "localhost"),
                "DISABLE_SERVER_SIDE_CURSORS": True,
                "PORT": os.getenv("PG_DATABASE_PORT", "5432"),
            }
        },
        environ=False,
    )

    # Use an in-process memory cache so throttle counters and response caches
    # do not persist across test runs (Redis would survive between runs and
    # accumulate throttle hits from previous executions within the same window).
    CACHES = values.DictValue(
        {
            "default": {
                "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                "LOCATION": "testing-cache",
                "KEY_PREFIX": "dozens-stg",
            }
        },
        environ=False,
    )

    REST_FRAMEWORK = values.DictValue(
        {
            **_REST_FRAMEWORK_DEV,
            "DEFAULT_THROTTLE_CLASSES": [],
            "DEFAULT_THROTTLE_RATES": {"anon": "1000/minute", "user": "1000/minute"},
        },
        environ=False,
    )

    @classmethod
    def configure_logging(cls):
        """CI (GitHub Actions commit checks): console only, warnings+ only,
        diagnostics disabled since they conflict with coverage tracing.
        Deliberately does not call Development's Loki-sending behavior.
        """
        if not cls.configure_logging_common():
            return
        logger.add(
            cls.DEFAULT_HANDLER,
            format=cls.LOG_FORMAT,
            level="WARNING",
            diagnose=False,
            catch=False,
            backtrace=False,
        )


# --- Coerce APPEND_COMPONENTS for all configurations ---
for _cfg in (Base, Production, Development, Offline, Staging):
    _cfg.SPECTACULAR_SETTINGS = _normalize_append_components(
        dict(_cfg.SPECTACULAR_SETTINGS)
    )
