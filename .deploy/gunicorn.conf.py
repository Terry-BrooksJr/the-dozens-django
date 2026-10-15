# gunicorn.conf.py
#
# Equivalent to your [gunicorn] INI config, but with post-fork hooks.
# This matters for SDKs that run background threads (like LaunchDarkly),
# because threads do not survive fork.
"""Gunicorn server configuration for the Django application.

Defines bind/worker settings, UTC millisecond log timestamps, Prometheus
multiprocess mode, and the post-fork hook that re-initializes thread-backed
SDKs in each worker.
"""

import logging
import os
import sys
import tempfile
import time

from gunicorn.glogging import Logger as GunicornLogger

# prometheus_client keeps metrics in per-process memory by default, so with
# several workers each /metrics scrape only saw whichever worker answered it,
# and max_requests recycling reset that worker's counters every ~1000
# requests. Multiprocess mode has every worker write to mmap'd files in a
# shared directory; django_prometheus's ExportToDjangoView (behind our
# /metrics view) switches to MultiProcessCollector automatically when
# PROMETHEUS_MULTIPROC_DIR is set, aggregating across all workers.
#
# on_starting() points PROMETHEUS_MULTIPROC_DIR at a directory owned by this
# master alone - "gunicorn-<master pid>" under the base below - so two masters
# sharing a base never read or clear each other's files, and cleanup never
# touches anything outside it. A PROMETHEUS_MULTIPROC_DIR set by the operator
# is used as the base. The original base is remembered in its own variable so
# a config reload (SIGHUP re-runs this file) doesn't nest directories.
PROMETHEUS_BASE_DIR = os.environ.setdefault(
    "DOZENS_PROMETHEUS_BASE_DIR",
    os.environ.get("PROMETHEUS_MULTIPROC_DIR")
    or os.path.join(
        "/dev/shm" if os.path.isdir("/dev/shm") else tempfile.gettempdir(),
        "dozens-prometheus",
    ),
)

# Gunicorn's own error log ordinarily reads server-local time via
# time.localtime() and has no way to render milliseconds through strftime
# (datefmt), so its timestamps drift from the app's own UTC+ms log format
# (see core.settings LOG_FORMAT). Fix both here so this takes effect even
# before the Django app (and its own converter override) is imported.
logging.Formatter.converter = time.gmtime


class UTCMillisecondLogger(GunicornLogger):
    """gunicorn's default error logger, with UTC + millisecond timestamps."""

    # %(msecs)03d is a plain LogRecord attribute, not part of datefmt/strftime,
    # so it works even though strftime itself can't format sub-second
    # precision. The offset is hardcoded since converter=time.gmtime above
    # guarantees these timestamps are always UTC.
    error_fmt = (
        r"[%(asctime)s.%(msecs)03d +0000] [%(process)d] [%(levelname)s] %(message)s"
    )
    datefmt = r"%Y-%m-%d %H:%M:%S"


logger_class = UTCMillisecondLogger

bind = "0.0.0.0:9555"
workers = 4  # 2 × nCPUs; 4 workers × 4 threads = 16 concurrent per replica
worker_class = "gthread"
threads = 4
# /dev/shm (a tmpfs, faster than disk for gunicorn's heartbeat file) only
# exists on Linux - the container this actually deploys to. Falling back to
# None lets gunicorn use its own default temp dir instead of crashing
# ("/dev/shm doesn't exist. Can't create workertmp.") when this config is
# loaded on a machine without it, e.g. running `task run:prod` locally on
# macOS.
worker_tmp_dir = "/dev/shm" if os.path.isdir("/dev/shm") else None
timeout = 60  # was 120; fail fast under burst so workers recycle sooner
graceful_timeout = 30
max_requests = 1000
max_requests_jitter = 100
loglevel = "info"

# gunicorn >=25.1 runs a control-socket server (for `gunicornc`) on a thread
# in the master, stopped before and restarted after every fork(). On macOS
# that still leaves the master multithreaded as far as the Objective-C
# runtime is concerned, so the first +initialize in a fresh worker (e.g.
# NSNumber, via urllib's _scproxy proxy lookup) aborts it with "may have been
# in progress in another thread when fork() was called" and the master logs
# "Worker was sent SIGKILL! Perhaps out of memory?". The first boot usually
# survives; every *replacement* worker then crashes in an endless loop.
# Nothing here uses gunicornc, and the Linux container is unaffected, so the
# socket is only disabled on macOS.
control_socket_disable = sys.platform == "darwin"

# Gunicorn expects this name in python config.
wsgi_app = "core.wsgi:application"

# NOT preloaded: LaunchDarkly Observability's OTel exporter opens a live
# gRPC channel during Django app init (applications.ld_integration.apps.
# LDIntegrationConfig.ready() -> configure_launchdarkly()). gRPC's C-core is
# not fork-safe - preloading (initializing the app once in the master, then
# forking workers from it) forks that live channel into every worker, which
# segfaults immediately after fork ("Worker was sent SIGSEGV", visible as
# gRPC's own "FD from fork parent still in poll list" just before it). This
# is not platform-specific; it reproduces on Linux the same way. ldclient
# (LaunchDarkly's feature-flag SDK proper) exposes postfork() specifically
# to recover from this under a preloaded master - see post_fork() below -
# but ldobserve's OTel/gRPC layer has no equivalent public API to reinit
# post-fork, so preloading can't be made safe here. Each worker instead
# performs its own full app init (including LaunchDarkly/ldobserve) after
# it's already a separate process, so no live gRPC channel is ever forked.
preload_app = False


def on_starting(server):
    """
    Give this master its own, empty Prometheus multiprocess directory.

    Runs in the master before any worker is forked, so every worker inherits
    the variable before it imports prometheus_client. Only prometheus_client's
    own *.db files are cleared - left behind if a previous master with the
    same pid (e.g. PID 1 in a restarted container) exited uncleanly.
    """
    from common.prometheus_multiproc import clear_metric_files

    path = os.path.join(PROMETHEUS_BASE_DIR, f"gunicorn-{os.getpid()}")
    os.makedirs(path, mode=0o700, exist_ok=True)
    os.environ["PROMETHEUS_MULTIPROC_DIR"] = path
    clear_metric_files(path)
    server.log.info(f"Prometheus multiprocess dir: {path}")


def child_exit(server, worker):
    """
    Fold a dead worker's metric files into the archive files.

    Keeps totals intact when max_requests recycles a worker, while keeping the
    directory (a size-limited tmpfs) at a bounded number of files instead of
    gaining two more for every worker that ever ran.
    """
    try:
        from common.prometheus_multiproc import compact_dead_process

        compact_dead_process(worker.pid)
    except Exception as e:
        server.log.warning(
            f"Prometheus compaction for worker {worker.pid} failed: {e!r}"
        )


def on_exit(server):
    """Remove this master's Prometheus files and directory on shutdown."""
    try:
        from common.prometheus_multiproc import multiproc_dir, remove_multiproc_dir

        path = multiproc_dir()
        if path:
            remove_multiproc_dir(path)
    except Exception as e:
        server.log.warning(f"Prometheus cleanup failed: {e!r}")


def worker_abort(worker):
    """
    Count a worker gunicorn is killing for exceeding ``timeout``.

    Runs inside the worker (on SIGABRT) just before it exits; the counter
    survives in the multiprocess archive via child_exit compaction.
    """
    try:
        from common.metrics import metrics

        metrics.record_worker_timeout()
    except Exception as e:
        worker.log.warning(f"Recording worker timeout failed: {e!r}")


def post_fork(server, worker):
    """
    Reinitialize SDKs that rely on background threads after fork.
    LaunchDarkly Python SDK specifically recommends calling postfork()
    in each worker process when using a preloaded master.
    """
    # LaunchDarkly postfork
    try:
        from applications.ld_integration.client import postfork_reinit

        postfork_reinit()
        worker.log.info("LaunchDarkly postfork() completed in worker")
    except Exception as e:
        worker.log.warning(f"LaunchDarkly postfork() failed in worker: {e!r}")
