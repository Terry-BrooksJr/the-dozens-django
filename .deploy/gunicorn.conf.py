# gunicorn.conf.py
#
# Equivalent to your [gunicorn] INI config, but with post-fork hooks.
# This matters for SDKs that run background threads (like LaunchDarkly),
# because threads do not survive fork.

import logging
import time

from gunicorn.glogging import Logger as GunicornLogger

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
worker_tmp_dir = "/dev/shm"
timeout = 60  # was 120; fail fast under burst so workers recycle sooner
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
