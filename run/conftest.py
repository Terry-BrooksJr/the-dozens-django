import os

from configurations import importer

# Must happen before Django imports settings
importer.install()

# Tell django-configurations which settings + class to use
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
os.environ.setdefault("DJANGO_CONFIGURATION", "Testing")  # change if your class name isn't Base