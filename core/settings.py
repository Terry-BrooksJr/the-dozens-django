# -*- coding: utf-8 -*-
"""
module: core.settings

Django settings for thedozens project.

"""

import contextlib
import json
import logging
import os
import sys
import threading
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import TextIO

try:
    import ldobserve.observe as observe
except ImportError:
    observe = None
from configurations import Configuration, values
from github import Github
from loguru import logger


# --- drf-spectacular postprocessing hook to inject TokenAuth without using APPEND_COMPONENTS ---
def add_token_auth_scheme(result, generator, request, public):
    """
    Add a TokenAuth security scheme to the generated OpenAPI schema. This hook ensures that token-based authentication is documented without requiring direct settings overrides.

    The function safely mutates the schema result to include an apiKey-based authorization header definition. It is designed to be resilient to schema generation errors and will silently fail if modifications cannot be applied.

    Args:
        result: The current OpenAPI schema representation being built or post-processed.
        generator: The schema generator instance invoking this hook.
        request: The HTTP request associated with schema generation, if available.
        public: A boolean indicating whether the schema is being generated for public consumption.

    Returns:
        The OpenAPI schema result with the TokenAuth security scheme injected when possible.
    """
    with contextlib.suppress(Exception):
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
    return result


def _normalize_append_components(settings_dict: dict) -> dict:
    """
    Normalize the APPEND_COMPONENTS value in a settings dictionary. This function ensures the configuration is always stored as a dictionary for consistent downstream usage.

    The function converts JSON string representations to dictionaries and replaces invalid or missing values with an empty dictionary. It returns the updated settings dictionary so that callers can work with a predictable APPEND_COMPONENTS structure.

    Args:
        settings_dict: A settings mapping that may contain an APPEND_COMPONENTS entry in various formats.

    Returns:
        The same settings dictionary with APPEND_COMPONENTS normalized to a dictionary.
    """
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
    """
    Format and route Python warning messages through the application's structured logger. This helper replaces the default warnings.showwarning to provide consistent, contextual log output.

    The function builds a single log line containing file, line number, warning category, message, and the original source line when available. It then emits the warning using the configured loguru logger at the warning level.

    Args:
        message: The warning message text to be logged.
        category: The class of the warning being emitted.
        filename: The name of the file where the warning originated.
        lineno: The line number in the source file where the warning was triggered.
        file: Optional file-like stream associated with the warning output, if any.
        line: Optional source code line that caused the warning, if available.

    Returns:
        None. The function performs logging as a side effect.
    """
    file_info = f" [{getattr(file, 'name', '')}]" if file else ""
    line_info = f" | {line.strip()}" if line else ""
    logger.warning(
        f"{filename}:{lineno}{file_info} - {category.__name__}: {message}{line_info}"
    )


# --- LaunchDarkly Observability: Loguru sink ---
# OpenTelemetry attributes must be primitives / sequences / mappings of primitives.
# Django sometimes attaches a full WSGIRequest object to log records (e.g., key "request").
# We strip/flatten that to safe values before sending to LaunchDarkly Observability.


def _otel_safe_value(value, *, _depth: int = 0):
    if value is None or isinstance(value, (bool, int, float, str, bytes)):
        return value

    # Avoid deep / huge structures
    if _depth >= 3:
        return str(value)

    if isinstance(value, (list, tuple, set)):
        return [_otel_safe_value(v, _depth=_depth + 1) for v in list(value)[:50]]

    if isinstance(value, dict):
        out = {}
        for k, v in list(value.items())[:50]:
            out[str(k)] = _otel_safe_value(v, _depth=_depth + 1)
        return out

    # Fallback: stringify unknown objects (e.g. WSGIRequest)
    return str(value)


def ld_loguru_sink(message):
    """Loguru sink that forwards logs to LaunchDarkly Observability safely."""
    record = message.record

    # Map Loguru level names to standard logging level numbers.
    level_name = record["level"].name
    level_map = {
        "TRACE": 5,
        "DEBUG": 10,
        "INFO": 20,
        "SUCCESS": 20,
        "WARNING": 30,
        "ERROR": 40,
        "CRITICAL": 50,
    }
    level_no = level_map.get(level_name, 20)

    attrs = {
        "logger.name": record.get("name"),
        "code.filepath": record.get("file").path if record.get("file") else None,
        "code.function": record.get("function"),
        "code.lineno": record.get("line"),
    }

    # Include Loguru extras, but ensure they are OTEL-safe.
    extra = dict(record.get("extra") or {})

    # Special-case Django request objects: flatten the useful bits.
    req = extra.pop("request", None)
    if req is not None:
        attrs["http.target"] = getattr(req, "path", None)
        attrs["http.method"] = getattr(req, "method", None)
        attrs["http.host"] = getattr(
            getattr(req, "get_host", None), "__call__", lambda: None
        )()

    for k, v in extra.items():
        attrs[str(k)] = _otel_safe_value(v)

    # Attach exception info if present
    exc = record.get("exception")
    if exc:
        attrs["exception.type"] = _otel_safe_value(getattr(exc, "type", None))
        attrs["exception.value"] = _otel_safe_value(getattr(exc, "value", None))
        attrs["exception.traceback"] = _otel_safe_value(getattr(exc, "traceback", None))

    # Remove nulls to keep payload clean
    attrs = {k: v for k, v in attrs.items() if v is not None}

    # Send to LaunchDarkly Observability (no-op if ldobserve is not installed)
    if observe is not None:
        observe.record_log(str(record.get("message")), level_no, attributes=attrs)


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
    logger_configured = False
    logger_lock = threading.Lock()

    @classmethod
    def configure_base_logger(cls) -> bool:
        """Configure the base logger exactly once per process.

        Returns:
            True if configuration should proceed (first caller).
            False if already configured.
        """
        with cls.logger_lock:
            if cls.logger_configured:
                return False
            cls.logger_configured = True
            return True

    @classmethod
    def get_github_api(cls):
        g = Github(cls.GITHUB_API_TOKEN)
        return g.get_repo(f"{cls.GITHUB_API_OWNER}/{cls.GITHUB_API_REPO}")

    ROOT_URLCONF = values.Value("core.urls", environ=False)
    WSGI_APPLICATION = values.Value("core.wsgi.application", environ=False)

    ADMINS = values.ListValue([("Terry Brooks", "Terry@BrooksJr.com")], environ=False)
    LANGUAGE_CODE = values.Value("en-us", environ=False)
    APPEND_SLASH = values.BooleanValue(True, environ=False)
    VIEW_CACHE_TTL = values.PositiveIntegerValue(
        environ=True, environ_prefix=None, environ_name="CACHE_TTL"
    )

    LAUNCHDARKLY_SDK_KEY = os.getenv("LAUNCHDARKLY_SDK_KEY")
    LAUNCHDARKLY_ENABLED = os.getenv("LAUNCHDARKLY_ENABLED").lower() == "true"
    LAUNCHDARKLY_OBSERVABILITY_ENABLED = os.getenv(
        "LAUNCHDARKLY_OBSERVABILITY_ENABLED", ""
    ).lower() in ("1", "true", "yes", "on")
    LAUNCHDARKLY_SERVICE_NAME = os.getenv("LAUNCHDARKLY_SERVICE_NAME")

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
    PRIMARY_LOG_FILE = Path(
        os.path.join(BASE_DIR, "logs", "primary_ops.log")
    )  # pyrefly: ignore
    CRITICAL_LOG_FILE = Path(
        os.path.join(BASE_DIR, "logs", "fatal.log")
    )  # pyrefly: ignore
    DEBUG_LOG_FILE = Path(
        os.path.join(BASE_DIR, "logs", "utility.log")
    )  # pyrefly: ignore
    DEBUG_PROPAGATE_EXCEPTIONS = True
    DEFAULT_HANDLER = sys.stdout
    with logger_lock:
        if not logger_configured:
            for _p in (PRIMARY_LOG_FILE, CRITICAL_LOG_FILE, DEBUG_LOG_FILE):
                _p.parent.mkdir(parents=True, exist_ok=True)

            logger.remove()
            warnings.filterwarnings("default")
            warnings.showwarning = log_warning

            # opentelemetry-instrumentation-logging forwards all Python log-record
            # extras to OTel as span/log attributes. Django's own loggers routinely
            # include `extra={"request": <WSGIRequest>}`, which OTel cannot
            # serialise and emits a WARNING for. Raising this logger's threshold to
            # ERROR silences that noise without hiding genuine OTel mis-use in our
            # own code.
            logging.getLogger("opentelemetry.attributes").setLevel(logging.ERROR)

            # File sinks: rotate daily, retain 30 days, compress rotated files.
            for file_sink in (PRIMARY_LOG_FILE, CRITICAL_LOG_FILE, DEBUG_LOG_FILE):
                logger.add(file_sink, **FILE_LOGGER_CONFIG)

            # Non-file sinks: no rotation/retention parameters.
            stream_sinks = [DEFAULT_HANDLER]
            if LAUNCHDARKLY_OBSERVABILITY_ENABLED:
                stream_sinks.append(ld_loguru_sink)
            for sink in stream_sinks:
                logger.add(sink, **DEFAULT_LOGGER_CONFIG)

            _logger_configured = True
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
        "VERSION": values.Value(
            environ=True, environ_prefix=None, environ_name="API_VERSION"
        ),
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
        "POSTPROCESSING_HOOKS": ["core.settings.add_token_auth_scheme"],
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
                    "CONNECTION_POOL_KWARGS": {"max_connections": 10},
                },
                "TIMEOUT": 300,
            },
        }
    )

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
    JAZZMIN_SETTINGS = {
        # title of the window (Will default to current_admin_site.site_title if absent or None)
        "site_title": "Yo Momma Jokes API",
        # Title on the login screen (19 chars max) (defaults to current_admin_site.site_header if absent or None)
        "site_header": "Yo Momma Jokes API",
        # Title on the brand (19 chars max) (defaults to current_admin_site.site_header if absent or None)
        "site_brand": "Yo Momma Jokes API",
        # Logo to use for your site, must be present in static files, used for brand on top left
        "site_logo": "https://dozens.nyc3.cdn.digitaloceanspaces.com/static/assets/yo_momma_brand.png",
        # Logo to use for your site, must be present in static files, used for login form logo (defaults to site_logo)
        "login_logo": "https://dozens.nyc3.cdn.digitaloceanspaces.com/static/assets/yo_momma_brand.png",
        # Logo to use for login form in dark themes (defaults to login_logo)
        "login_logo_dark": "https://dozens.nyc3.cdn.digitaloceanspaces.com/static/assets/yo_momma_brand.png",
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
        "hide_apps": [],
        # Hide these models when generating side menu (e.g auth.user)
        "hide_models": [],
        # List of apps (and/or models) to base side menu ordering off of (does not need to contain all apps/models)
        "order_with_respect_to": ["auth", "books", "books.author", "books.book"],
        # Custom icons for side menu apps/models See https://fontawesome.com/icons?d=gallery&m=free&v=5.0.0,5.0.1,5.0.10,5.0.11,5.0.12,5.0.13,5.0.2,5.0.3,5.0.4,5.0.5,5.0.6,5.0.7,5.0.8,5.0.9,5.1.0,5.1.1,5.2.0,5.3.0,5.3.1,5.4.0,5.4.1,5.4.2,5.13.0,5.12.0,5.11.2,5.11.1,5.10.0,5.9.0,5.8.2,5.8.1,5.7.2,5.7.1,5.7.0,5.6.3,5.5.0,5.4.2
        # for the full list of 5.13.0 free icon classes
        "icons": {
            "auth": "fas fa-users-cog",
            "auth.user": "fas fa-user",
            "auth.Group": "fas fa-users",
            "applications.API.Insult": "fa-regular fa-face-grin-tongue-wink",
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
    INSTALLED_APPS = values.ListValue(
        [
            # 0) Instrumentation that wants to wrap others early
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
            # 2) DRF UI skin — must come BEFORE rest_framework so Django's template
            #    loader finds rest_wind's rest_framework/base.html first
            "rest_wind",
            # 3) Core framework add-ons (foundation pieces)
            "rest_framework",
            "rest_framework.authtoken",
            "django_filters",
            # 4) Third-party apps (features)
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
            # 6) Your project apps (stuff you own)
            "applications.API",
            "applications.graphQL",
            "applications.ld_integration",
        ],
        environ=False,
    )

    MIDDLEWARE = values.ListValue(
        [
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
            "applications.ld_integration.middleware.LaunchDarklyContextMiddleware",
            "common.middleware.RequestIDMiddleware",
        ],
        environ=False,
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
            "https://dozens.nyc3.cdn.digitaloceanspaces.com/*",
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

    if Base._logger_configured:
        logger.remove()


class Offline(Base):
    INTERNAL_IPS = ["*"]
    ALLOWED_HOSTS = ["*"]
    DEBUG = True
    CORS_ALLOW_ALL_ORIGINS = True
    # Allow any origin in the local Docker environment so admin works regardless
    # of which hostname/port is used to reach the container.
    CSRF_TRUSTED_ORIGINS = ["http://localhost:*", "http://127.0.0.1:*", "http://*"]
    STATIC_URL = "/static/"
    STATICFILES_DIRS = [
        os.path.join(BASE_DIR, "static"),
    ]
    STORAGES = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }
    INSTALLED_APPS = values.ListValue(
        [
            # 0) Instrumentation that wants to wrap others early
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
            # 2) DRF UI skin — must come BEFORE rest_framework so Django's template
            #    loader finds rest_wind's rest_framework/base.html first
            "rest_wind",
            # 3) Core framework add-ons (foundation pieces)
            "rest_framework",
            "rest_framework.authtoken",
            "django_filters",
            # 4) Third-party apps (features)
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
            # 6) Dev-only tooling
            "debug_toolbar",
            # 7) Your project apps (stuff you own)
            "applications.API",
            "applications.graphQL",
            "applications.ld_integration",
        ],
        environ=False,
    )

    MIDDLEWARE = values.ListValue(
        [
            "django_prometheus.middleware.PrometheusBeforeMiddleware",
            "corsheaders.middleware.CorsMiddleware",
            "django.middleware.cache.UpdateCacheMiddleware",
            "django.middleware.security.SecurityMiddleware",
            "whitenoise.middleware.WhiteNoiseMiddleware",
            "django.contrib.sessions.middleware.SessionMiddleware",
            "django.middleware.common.CommonMiddleware",
            "debug_toolbar.middleware.DebugToolbarMiddleware",
            "django.middleware.csrf.CsrfViewMiddleware",
            "django.contrib.auth.middleware.AuthenticationMiddleware",
            "django.contrib.messages.middleware.MessageMiddleware",
            "django.middleware.clickjacking.XFrameOptionsMiddleware",
            "django.middleware.cache.FetchFromCacheMiddleware",
            "django_prometheus.middleware.PrometheusAfterMiddleware",
            "common.middleware.RequestIDMiddleware",
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
    STATIC_URL = "/static/"
    STATICFILES_DIRS = [
        os.path.join(BASE_DIR, "static"),
    ]
    STORAGES = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }
    INSTALLED_APPS = values.ListValue(
        [
            # 0) Instrumentation that wants to wrap others early
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
            # 2) DRF UI skin — must come BEFORE rest_framework so Django's template
            #    loader finds rest_wind's rest_framework/base.html first
            "rest_wind",
            # 3) Core framework add-ons (foundation pieces)
            "rest_framework",
            "rest_framework.authtoken",
            "django_filters",
            # 4) Third-party apps (features)
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
            # 6) Dev-only tooling
            "debug_toolbar",
            # 7) Your project apps (stuff you own)
            "applications.API",
            "applications.graphQL",
            "applications.ld_integration",
        ],
        environ=False,
    )

    MIDDLEWARE = values.ListValue(
        [
            "django_prometheus.middleware.PrometheusBeforeMiddleware",
            "corsheaders.middleware.CorsMiddleware",
            "django.middleware.cache.UpdateCacheMiddleware",
            "django.middleware.security.SecurityMiddleware",
            "whitenoise.middleware.WhiteNoiseMiddleware",
            "django.contrib.sessions.middleware.SessionMiddleware",
            "django.middleware.common.CommonMiddleware",
            "debug_toolbar.middleware.DebugToolbarMiddleware",
            "django.middleware.csrf.CsrfViewMiddleware",
            "django.contrib.auth.middleware.AuthenticationMiddleware",
            "django.contrib.messages.middleware.MessageMiddleware",
            "django.middleware.clickjacking.XFrameOptionsMiddleware",
            "django.middleware.cache.FetchFromCacheMiddleware",
            "django_prometheus.middleware.PrometheusAfterMiddleware",
            "applications.ld_integration.middleware.LaunchDarklyContextMiddleware",
            "common.middleware.RequestIDMiddleware",
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

    # Use an in-process memory cache so throttle counters and response caches
    # do not persist across test runs (Redis would survive between runs and
    # accumulate throttle hits from previous executions within the same window).
    CACHES = values.DictValue(
        {
            "default": {
                "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                "LOCATION": "testing-cache",
            }
        },
        environ=False,
    )

    # Explicitly disable all throttle classes so no test ever receives a 429.
    # Development leaves DEFAULT_THROTTLE_CLASSES absent (relying on DRF's
    # default of []), but keeping DEFAULT_THROTTLE_RATES in the inherited dict
    # alongside a persistent Redis cache can still produce spurious 429s when
    # tests are re-run within the throttle window.
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
            "DEFAULT_THROTTLE_CLASSES": [],
            "DEFAULT_THROTTLE_RATES": {"anon": "1000/minute", "user": "1000/minute"},
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


# Configure logger for Testing environment
# Must be done at module level AFTER class definition
# Disable loguru's diagnostic features to avoid conflicts with coverage tracing
if os.getenv("DJANGO_CONFIGURATION") == "Testing" and Base.configure_base_logger():
    logger.remove()
    logger.add(
        Base.DEFAULT_HANDLER,
        format=Base.LOG_FORMAT,
        level="WARNING",
        diagnose=False,
        catch=False,
        backtrace=False,
    )


# --- Coerce APPEND_COMPONENTS for all configurations ---
for _cfg in (Base, Production, Development, Offline, Testing):
    _cfg.SPECTACULAR_SETTINGS = _normalize_append_components(
        dict(_cfg.SPECTACULAR_SETTINGS)
    )
