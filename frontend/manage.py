#!/usr/bin/env python


import os
import sys

from django.core.management import execute_from_command_line


try:
    import autotest.common as common
except ImportError:
    import common


if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "autotest.frontend.settings")
    execute_from_command_line(sys.argv)
