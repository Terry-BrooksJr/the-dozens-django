"""
mypy runner for django-configurations projects.

django-stubs calls django.setup() at plugin load time, which imports
core.settings.  The Base(Configuration) metaclass requires the
django-configurations importer to be installed first — identical to
the pytest bootstrapping problem solved in pytest_dozens_plugin.py.

Usage (from Taskfile):
    .venv/bin/python run/mypy_runner.py <mypy args...>
"""

import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
os.environ.setdefault("DJANGO_CONFIGURATION", "Staging")
os.environ.setdefault("POSTGRES_DB", "mypy")
os.environ.setdefault("PG_DATABASE_USER", "mypy")
os.environ.setdefault("PG_DATABASE_PASSWORD", "mypy")
os.environ.setdefault("PG_DATABASE_HOST", "localhost")
os.environ.setdefault("PG_DATABASE_PORT", "5432")

from configurations import importer  # noqa: E402

importer.install()

from mypy import api  # noqa: E402

stdout, stderr, exit_code = api.run(sys.argv[1:])
if stdout:
    print(stdout, end="")
if stderr:
    print(stderr, end="", file=sys.stderr)
sys.exit(exit_code)
