# -*- coding: utf-8 -*-
"""
Root pytest configuration for the-dozens-django.

Bootstrap note
--------------
django-configurations requires ``importer.install()`` to run — with
``DJANGO_SETTINGS_MODULE`` and ``DJANGO_CONFIGURATION`` already set in
``os.environ`` — before Django loads ``core.settings``.

This cannot be done here: conftest files are discovered *during*
``pytest_load_initial_conftests``, so any hook defined in this file fires
inside that phase, not before it — too late to beat pytest-django.

The bootstrap is handled by ``pytest_dozens_plugin.py``, a named plugin
loaded via ``addopts = ["-p", "pytest_dozens_plugin"]`` in
``[tool.pytest.ini_options]``.  Plugins registered through ``-p`` are
registered at argument-parse time, before any conftest discovery, so their
``pytest_load_initial_conftests(tryfirst=True)`` hook is guaranteed to run
first.

This file is intentionally kept free of bootstrap logic; add project-wide
fixtures here as needed.
"""
