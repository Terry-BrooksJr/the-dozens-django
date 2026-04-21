# -*- coding: utf-8 -*-
"""
pytest plugin: pytest_dozens_plugin
------------------------------------
Loaded via ``addopts = ["-p", "pytest_dozens_plugin"]`` in
``[tool.pytest.ini_options]``.  Plugins loaded this way are registered
*before* pytest discovers and loads conftest files, which means this
``pytest_load_initial_conftests`` hook is guaranteed to run before
pytest-django's implementation of the same hook.

Why this matters
----------------
pytest-django's ``pytest_load_initial_conftests`` accesses
``django.conf.settings.DATABASES``, triggering Django to import
``core.settings``.  ``core.settings`` defines ``class Base(Configuration)``
whose metaclass checks that the django-configurations importer is already
installed — raising ``ImproperlyConfigured`` if it isn't.

A root ``conftest.py`` hook can't help because conftest files are
discovered *during* ``pytest_load_initial_conftests``, not before.
A named plugin loaded via ``-p`` is the only mechanism that fires early
enough to install the importer first.
"""

import os

import pytest


@pytest.hookimpl(tryfirst=True)
def pytest_load_initial_conftests(early_config, parser, args):  # noqa: ARG001
    """Install django-configurations importer before pytest-django reads settings."""
    # Environment variables must be set BEFORE importer.install() because
    # install() calls validate(), which raises ImproperlyConfigured if
    # DJANGO_CONFIGURATION is not already defined.
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
    os.environ.setdefault("DJANGO_CONFIGURATION", "Testing")

    from configurations import importer

    importer.install()
