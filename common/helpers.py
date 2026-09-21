# -*- coding: utf-8 -*-
"""
module: common.helpers

Free-standing helper functions used by core.settings: a drf-spectacular
schema postprocessing hook, a settings-dict normalizer, and the
Loguru/LaunchDarkly logging glue (a stdlib `warnings` hook, a UTC time
patcher, and the sink that forwards log records to LaunchDarkly
Observability). Kept out of core/settings.py so that module stays focused on
declarative Django configuration.
"""

import contextlib
import contextvars
import inspect
import json
import logging
from datetime import timezone
from typing import TextIO

try:
    import ldobserve.observe as observe
except ImportError:
    observe = None

from loguru import logger
from loki_logger_handler.formatters.loguru_formatter import LoguruFormatter


# --- drf-spectacular postprocessing hook to inject TokenAuth without using APPEND_COMPONENTS ---
def add_token_auth_scheme(result, **kwargs):
    """
    Add a TokenAuth security scheme to the generated OpenAPI schema. This hook ensures that token-based authentication is documented without requiring direct settings overrides.

    The function safely mutates the schema result to include an apiKey-based authorization header definition. It is designed to be resilient to schema generation errors and will silently fail if modifications cannot be applied.

    Args:
        result: The current OpenAPI schema representation being built or post-processed.
        **kwargs: drf-spectacular's other postprocessing hook arguments
            (`generator`, `request`, `public`), unused here - accepted only
            because drf-spectacular always calls hooks with all four as
            keyword arguments.

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
            settings_dict["APPEND_COMPONENTS"] = parsed
        except Exception:
            settings_dict["APPEND_COMPONENTS"] = {}
    if not isinstance(settings_dict.get("APPEND_COMPONENTS"), dict):
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


def _insert_after_middleware(base, after_item, *new_items):
    """Return a copy of *base* with *new_items* inserted after *after_item*."""
    result = list(base)
    try:
        idx = result.index(after_item) + 1
    except ValueError:
        raise ValueError(
            f"Middleware {after_item!r} not found in the base middleware list. "
            f"Was it renamed or removed?"
        ) from None
    for i, item in enumerate(new_items):
        result.insert(idx + i, item)
    return result


def _force_utc_time(record: dict) -> None:
    """Loguru patcher: log timestamps in UTC regardless of TIME_ZONE/server tz."""
    record["time"] = record["time"].astimezone(timezone.utc)


def _loguru_icon_for(level_name: str) -> str:
    """Look up a level's emoji icon from Loguru itself.

    Keeps `StdlibLoguruStyleFormatter` in sync with whatever Loguru actually
    uses for a level (including any custom `logger.level(...)` registration)
    instead of hardcoding a second copy of the icon mapping. Falls back to
    two blank spaces for level names Loguru doesn't know - e.g. the
    deprecated `WARN` alias, or a third-party library's custom level - so a
    lookup miss can't break the log call.
    """
    try:
        return logger.level(level_name).icon
    except ValueError:
        return "  "


class StdlibLoguruStyleFormatter(logging.Formatter):
    """Stdlib `logging.Formatter` that visually matches Loguru's console `LOG_FORMAT`.

    Used directly by `InterceptHandler` as the fallback path for loggers it
    deliberately doesn't bridge into Loguru (see `_UNBRIDGED_LOGGER_PREFIXES`)
    so those records still render with a matching icon/timestamp instead of
    whatever bare default formatting stdlib logging would otherwise use.
    """

    # Stdlib's own default ("%s,%03d") uses a comma; Loguru's {time:...SSS}
    # token renders a period, which is the mismatch this formatter exists to
    # fix.
    default_msec_format = "%s.%03d"

    def __init__(self) -> None:
        super().__init__(
            fmt="%(asctime)sZ | %(icon)s  %(levelname)-8s | [%(name)s] - %(message)s"
        )

    def format(self, record: logging.LogRecord) -> str:
        record.icon = _loguru_icon_for(record.levelname)
        return super().format(record)


# Set while InterceptHandler is forwarding a record into Loguru. Guards
# against unbounded recursion: if something in Loguru's sink pipeline (an
# exporter error, a validation warning) emits a *new* stdlib log record
# synchronously while we're still inside that forward call, this makes the
# reentrant emit() a no-op instead of forwarding forever. Mirrors the same
# guard ldobserve's own root-logger handler uses for the identical reason
# (see ldobserve._otel.logging_handler.LDLoggingHandler) - a ContextVar
# rather than instance state so it also covers reentrancy across multiple
# InterceptHandler instances, if more than one is ever installed.
_bridging_stdlib_record: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "helpers_bridging_stdlib_record", default=False
)


# Loggers excluded from the Loguru bridge below and routed through a plain
# stdlib formatter instead. Both are the observability/tracing SDK's own
# internal machinery: ldobserve.observe._use_instance() logs a warning
# (`logging.getLogger(__name__).warning(...)`) whenever anything - including
# ldobserve's own background export/init code - calls into the observability
# singleton before it's finished initializing, which happens routinely
# during startup; opentelemetry's exporters carry the identical shape of
# risk (see ldobserve._otel.logging_handler's own module docstring on
# foreign-instrumentation feedback loops). Bridging that specific call
# through Loguru is what turns a harmless startup-ordering warning into a
# same-thread reentrant `logger.log()` call while Loguru is already
# mid-dispatch for the *same* record on a sink that itself touches the SDK
# (e.g. ld_loguru_sink -> observe.record_log) - Loguru refuses that
# (`Could not acquire internal lock ... deadlock avoided`) and prints a
# diagnostic instead of crashing, but the noise recurs on every occurrence.
# These loggers are also already exported to LaunchDarkly Observability
# independently via the SDK's own LDLoggingHandler (see ld_loguru_sink's
# docstring), so nothing is lost by keeping them off the Loguru bridge -
# ldclient (LaunchDarkly's feature-flag SDK proper) is unaffected and still
# bridges normally.
_UNBRIDGED_LOGGER_PREFIXES = ("ldobserve", "opentelemetry")

_fallback_console_handler = logging.StreamHandler()
_fallback_console_handler.setFormatter(StdlibLoguruStyleFormatter())


class InterceptHandler(logging.Handler):
    """Bridges stdlib `logging` records into Loguru's own sinks.

    Third-party libraries (ldobserve, ldclient, django, gunicorn, ...) log via
    the stdlib `logging` module, not Loguru, so - without this - their
    records never reach Loguru's sinks (console, file, Loki, LaunchDarkly
    Observability): they're confined to whatever plain handler sits on the
    stdlib root logger. Installing this as that root handler (see
    `applications.ld_integration.apps.LDIntegrationConfig.ready`) makes every
    stdlib log record flow through the exact same pipeline as our own
    `loguru.logger` calls, console icon/format included - except records
    from `_UNBRIDGED_LOGGER_PREFIXES` (see its comment), which fall back to
    a plain, non-Loguru console formatter to avoid a reentrant-logging risk
    specific to the observability SDK's own internals.

    Forwarded records are tagged `extra={"_bridged_from_stdlib": True}` so
    `ld_loguru_sink` can skip re-exporting them to LaunchDarkly Observability:
    the SDK's own `LDLoggingHandler` is *also* attached directly to the
    stdlib root logger (see `ldobserve._otel.configuration`) and already
    exports every root-logger record there independently via OTel -
    forwarding the same record through `ld_loguru_sink` too would double
    report it. Console/file/Loki sinks still receive these records normally;
    only the LaunchDarkly Observability export is deduplicated.
    """

    def emit(self, record: logging.LogRecord) -> None:
        if record.name.split(".", 1)[0] in _UNBRIDGED_LOGGER_PREFIXES:
            _fallback_console_handler.emit(record)
            return
        if _bridging_stdlib_record.get():
            return
        token = _bridging_stdlib_record.set(True)
        try:
            self._forward(record)
        finally:
            _bridging_stdlib_record.reset(token)

    @staticmethod
    def _forward(record: logging.LogRecord) -> None:
        try:
            level: int | str = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Walk past stdlib logging's own call frames *and* this handler's own
        # (emit -> _forward) so Loguru attributes the message to the original
        # caller's file/function/line, not to logging.Logger.callHandlers or
        # to this bridge. (The standard Loguru <-> stdlib logging recipe only
        # skips logging.__file__ frames, because it defines emit() to call
        # logger.log() directly; the extra _forward() indirection here means
        # this module's own frames need skipping too.)
        frame, depth = inspect.currentframe(), 0
        while frame and frame.f_code.co_filename in (logging.__file__, __file__):
            frame = frame.f_back
            depth += 1

        # {name} in Loguru's own format is derived from the resolved caller
        # frame above, not from the stdlib logger's `.name` - bind that
        # separately so it isn't lost for sinks that want it (e.g. Loki).
        logger.bind(_bridged_from_stdlib=True, stdlib_logger_name=record.name).opt(
            depth=depth, exception=record.exc_info
        ).log(level, record.getMessage())


# --- LaunchDarkly Observability: Loguru sink ---
# OpenTelemetry attributes must be primitives / sequences / mappings of primitives.
# Django sometimes attaches a full WSGIRequest object to log records (e.g., key "request").
# We strip/flatten that to safe values before sending to LaunchDarkly Observability.


def _otel_safe_value(value, *, _depth: int = 0):
    """
    Recursively coerce an arbitrary value into an OpenTelemetry-safe form.

    OTel attributes must be primitives (or sequences/mappings of primitives).
    This walks lists/tuples/sets/dicts, truncates them to 50 items to avoid
    huge payloads, stringifies anything beyond a depth of 3 to avoid runaway
    recursion, and falls back to `str()` for unrecognized object types (e.g.
    a Django WSGIRequest that ends up in `extra`).

    Args:
        value: The value to sanitize.
        _depth: Internal recursion depth guard; callers should not set this.

    Returns:
        A primitive, or a list/dict of primitives, safe to hand to OTel.
    """
    if value is None or isinstance(value, (bool, int, float, str)):
        return value

    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")

    # Avoid deep / huge structures
    if _depth >= 3:
        return str(value)

    if isinstance(value, (list, tuple, set)):
        return [_otel_safe_value(v, _depth=_depth + 1) for v in list(value)[:50]]

    if isinstance(value, dict):
        return {
            str(k): _otel_safe_value(v, _depth=_depth + 1)
            for k, v in list(value.items())[:50]
        }
    # Fallback: stringify unknown objects (e.g. WSGIRequest)
    return str(value)


def _safe_get_host(req) -> str | None:
    """request.get_host() raises DisallowedHost for a bad/missing Host header;
    a log sink must never raise, or it can take the log call down with it.
    """
    get_host = getattr(req, "get_host", None)
    if get_host is None:
        return None
    with contextlib.suppress(Exception):
        return get_host()
    return None


def ld_loguru_sink(message):
    """
    Loguru sink that forwards a log record to LaunchDarkly Observability.

    Maps the Loguru level name to a standard `logging` level number, builds a
    small set of OTel-style attributes (logger name, source file/function/
    line), flattens a Django request found under the `request` extra key into
    `http.*` attributes, sanitizes any remaining `extra` values via
    `_otel_safe_value`, and attaches exception info when present. Silently
    no-ops if `ldobserve` is not installed, and never raises - a log sink
    failure must not take down the caller that logged the message.

    Skips records `InterceptHandler` bridged in from stdlib `logging`
    (tagged `extra={"_bridged_from_stdlib": True}`): those already reach
    LaunchDarkly Observability independently, via the SDK's own
    `LDLoggingHandler` on the stdlib root logger, so forwarding them here
    too would double-report every third-party log line.

    Args:
        message: A Loguru `Message` object; `message.record` holds the
            structured log data (level, name, file, function, line, extra,
            exception, message).

    Returns:
        None. Forwards the record to `observe.record_log` as a side effect.
    """
    record = message.record

    if record.get("extra", {}).get("_bridged_from_stdlib"):
        return

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
        attrs["http.host"] = _safe_get_host(req)

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
        with contextlib.suppress(Exception):
            observe.record_log(str(record.get("message")), level_no, attributes=attrs)


class SanitizingLoguruFormatter(LoguruFormatter):
    """`LoguruFormatter` that guarantees its output is JSON-serializable.

    `loki_logger_handler`'s own `LoguruFormatter.format()` merges Loguru's
    `extra` dict straight into the record it later hands to
    `json.dumps()` (in `loki_logger_handler.stream.Stream.append_value`).
    Anything bound via `logger.bind(...)` that isn't a JSON primitive - a
    Django/DRF request, a model instance, an exception - survives that merge
    untouched and blows up `json.dumps()` on `LokiLoggerHandler`'s background
    flush thread, which surfaces as an unhandled exception in an `atexit`
    callback (the flush thread reports errors there since callers never see
    it synchronously). Route every top-level value through the same
    sanitizer already used for the LaunchDarkly Observability sink so that
    can never happen, regardless of what a future `logger.bind(...)` call
    attaches.
    """

    def format(self, record):
        formatted, loki_metadata = super().format(record)
        formatted = {k: _otel_safe_value(v) for k, v in formatted.items()}
        if loki_metadata:
            loki_metadata = {k: _otel_safe_value(v) for k, v in loki_metadata.items()}
        return formatted, loki_metadata
