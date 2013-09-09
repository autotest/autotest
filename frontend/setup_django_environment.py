import os

#
# Django >= 1.4 makes the setup of a particular setting this simple. And yes,
# this is the recommended way to do it.
#
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "autotest.frontend.settings")


def enable_autocommit():
    from django.db import connection
    connection.cursor()  # ensure a connection is open
    connection.connection.autocommit(True)
