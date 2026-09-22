# -*- coding: utf-8 -*-
"""
Project-wide pytest configuration for the-dozens-django.

Location note
-------------
This file lives in ``.configs/``, not repo root, so pytest's normal
conftest.py auto-discovery (walking up from each test file's location to
rootdir) never finds it — ``.configs`` isn't an ancestor of
``applications/``, ``common/``, etc. It's loaded explicitly instead, via
``addopts = ["-p", "pytest_dozens_plugin", "-p", "conftest"]`` in
``[tool.pytest.ini_options]`` (``.configs`` is added to ``pythonpath`` there
so both bare module names resolve) — the same mechanism
``pytest_dozens_plugin.py`` uses, and for the same reason: nothing else can
find a module outside the directories pytest actually walks.

Bootstrap note
--------------
django-configurations requires ``importer.install()`` to run — with
``DJANGO_SETTINGS_MODULE`` and ``DJANGO_CONFIGURATION`` already set in
``os.environ`` — before Django loads ``core.settings``. That bootstrap
can't live here even though this file is now `-p`-loaded like
``pytest_dozens_plugin.py``: ``pytest_load_initial_conftests`` fires once,
and ``pytest_dozens_plugin`` already claims it with
``@pytest.hookimpl(tryfirst=True)`` specifically to win the race against
pytest-django's own implementation of that hook. It stays there.

This file is intentionally kept free of bootstrap logic; add project-wide
fixtures here as needed.
"""
