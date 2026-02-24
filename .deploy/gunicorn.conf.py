# gunicorn.conf.py
#
# Equivalent to your [gunicorn] INI config, but with post-fork hooks.
# This matters for SDKs that run background threads (like LaunchDarkly),
# because threads do not survive fork.

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
