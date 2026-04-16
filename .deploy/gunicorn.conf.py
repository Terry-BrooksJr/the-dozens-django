# gunicorn.conf.py
#
# Equivalent to your [gunicorn] INI config, but with post-fork hooks.
# This matters for SDKs that run background threads (like LaunchDarkly),
# because threads do not survive fork.

import os
import shutil

# ---------------------------------------------------------------------------
# Prometheus multiprocess mode
# ---------------------------------------------------------------------------
# Must be set BEFORE prometheus_client metric objects are constructed.
# preload_app=True means the master imports the app (and all metric objects)
# before forking workers, so this module-level assignment is the right place.
# Using /dev/shm (tmpfs) matches worker_tmp_dir — avoids disk I/O for counters.
_PROM_DIR = os.environ.setdefault("PROMETHEUS_MULTIPROC_DIR", "/dev/shm/prom_multiproc")
# prometheus_client also accepts the lowercase spelling; set both to be safe.
os.environ.setdefault("prometheus_multiproc_dir", _PROM_DIR)
# ---------------------------------------------------------------------------

bind = "0.0.0.0:9090"
workers = 2
worker_class = "gthread"
threads = 4
worker_tmp_dir = "/dev/shm"
timeout = 120
graceful_timeout = 30
max_requests = 1000
max_requests_jitter = 100
loglevel = "info"

# Gunicorn expects this name in python config.
wsgi_app = "core.wsgi:application"

# Important for worker-based servers: initialize app in master before fork,
# then run post_fork hook in each worker.
preload_app = True


def on_starting(server):
    """
    Called once in the master process before workers are forked.

    Wipe and recreate the prometheus multiproc dir so stale per-pid files
    from a previous run don't pollute aggregated metrics.
    """
    if os.path.isdir(_PROM_DIR):
        shutil.rmtree(_PROM_DIR)
    os.makedirs(_PROM_DIR, exist_ok=True)
    server.log.info(f"Prometheus multiproc dir initialised: {_PROM_DIR}")


def child_exit(server, worker):
    """
    Called in the master process when a worker exits (crash or graceful).

    prometheus_client writes per-pid gauge files under PROMETHEUS_MULTIPROC_DIR.
    Calling mark_process_dead removes that worker's files so the /metrics
    aggregator doesn't keep including stale gauge values from a dead pid.
    """
    try:
        from prometheus_client import multiprocess

        multiprocess.mark_process_dead(worker.pid)
    except Exception as e:
        server.log.warning(f"prometheus mark_process_dead failed: {e!r}")


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
