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
import shutil
import sys
import tempfile
import time

from gunicorn.glogging import Logger as GunicornLogger

# prometheus_client keeps metrics in per-process memory by default, so with
# several workers each /metrics scrape only saw whichever worker answered it,
# and max_requests recycling reset that worker's counters every ~1000
# requests. Multiprocess mode has every worker write to mmap'd files in a
# shared directory; django_prometheus's ExportToDjangoView (behind our
# /metrics view) switches to MultiProcessCollector automatically when this
# env var is set, aggregating across all workers. It must be set before any
# worker imports prometheus_client - setting it here, in the master, before
# fork, guarantees that. The directory is (re)created in on_starting().
PROMETHEUS_MULTIPROC_DIR = os.environ.setdefault(
    "PROMETHEUS_MULTIPROC_DIR",
    os.path.join(
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
    Start every master with an empty Prometheus multiprocess directory.

    Files left by a previous run (same container restarted, or a local run)
    would otherwise be summed into the new run's counters.
    """
    shutil.rmtree(PROMETHEUS_MULTIPROC_DIR, ignore_errors=True)
    os.makedirs(PROMETHEUS_MULTIPROC_DIR, exist_ok=True)


def child_exit(server, worker):
    """
    Tell prometheus_client a worker is gone.

    Counters and histograms from the dead worker's files are kept (so totals
    don't drop when max_requests recycles it); this only removes its
    live-gauge series.
    """
    try:
        from prometheus_client import multiprocess

        multiprocess.mark_process_dead(worker.pid)
    except Exception as e:
        server.log.warning(f"Prometheus mark_process_dead() failed: {e!r}")


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
