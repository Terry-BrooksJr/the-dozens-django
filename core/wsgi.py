# -*- coding: utf-8 -*-
"""
WSGI config for thedozens project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/wsgi/
"""

import os
import tempfile

from configurations.wsgi import get_wsgi_application

TEMP_STATIC_DIR = tempfile.mkdtemp()
os.environ.setdefault("TEMP_STATIC_DIR", TEMP_STATIC_DIR)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
os.environ.setdefault("DJANGO_CONFIGURATION", "Production")


application = get_wsgi_application()
