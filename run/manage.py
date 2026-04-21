#!/usr/bin/env python

import os
import sys

print("EXECUTABLE:", sys.executable)
print("DOPPLER_ENV:", os.getenv("DOPPLER_ENV"))
print("DOPPLER_PROJECT:", os.getenv("DOPPLER_PROJECT"))
print("SECRET_KEY exists:", bool(os.getenv("SECRET_KEY")))
# Add the parent directory to the Python path so we can import core
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
    os.environ.setdefault("DJANGO_CONFIGURATION", "Production")

    from configurations.management import execute_from_command_line

    execute_from_command_line(sys.argv)
