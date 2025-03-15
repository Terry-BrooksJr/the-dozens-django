#!/usr/bin/env python

import os
import sys

is_testing = "test" in sys.argv
if is_testing:
    import coverage

    cov = coverage.coverage(source=["app"], omit=["*/tests/*"])
    cov.set_option("report:show_missing", True)
    cov.erase()
    cov.start()

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
    os.environ.setdefault("DJANGO_CONFIGURATION", "Production")

    from configurations.management import execute_from_command_line

    execute_from_command_line(sys.argv)

    if is_testing:
        cov.stop()
        cov.save()
        cov.report()
