# Django settings for frontend project.

import os
try:
    import autotest.common as common
except ImportError:
    import common
from autotest.client.shared.settings import settings

_section = 'AUTOTEST_WEB'

DEBUG = settings.get_value(_section, "sql_debug_mode", type=bool, default=False)
TEMPLATE_DEBUG = settings.get_value(_section, "template_debug_mode", type=bool,
                                    default=False)

FULL_ADMIN = False

ADMINS = (
    # ('Your Name', 'your_email@domain.com'),
)

MANAGERS = ADMINS


def _get_config(config_key, default=None):
    return settings.get_value(_section, config_key, default=default)

AUTOTEST_DEFAULT = {
    'ENGINE': 'autotest.frontend.db.backends.afe',
    'PORT': '',
    'HOST': _get_config("host"),
    'NAME': _get_config("database"),
    'USER': _get_config("user"),
    'PASSWORD': _get_config("password", default=''),
    'READONLY_HOST': _get_config("readonly_host", default=_get_config("host")),
    'READONLY_USER': _get_config("readonly_user", default=_get_config("user"))}

if AUTOTEST_DEFAULT['READONLY_USER'] != AUTOTEST_DEFAULT['USER']:
    AUTOTEST_DEFAULT['READONLY_PASSWORD'] = _get_config("readonly_password",
                                                        default='')
else:
    AUTOTEST_DEFAULT['READONLY_PASSWORD'] = AUTOTEST_DEFAULT['PASSWORD']

SOUTH_BACKENDS = {
    'autotest.frontend.db.backends.afe': 'south.db.mysql',
    'autotest.frontend.db.backends.afe_sqlite': 'south.db.sqlite3'
}

SOUTH_DATABASE_ADAPTERS = {
    'default': SOUTH_BACKENDS[AUTOTEST_DEFAULT['ENGINE']]
}

DATABASES = {'default': AUTOTEST_DEFAULT}

# Local time zone for this installation. Choices can be found here:
# http://www.postgresql.org/docs/8.1/static/datetime-keywords.html#DATETIME-TIMEZONE-SET-TABLE
# although not all variations may be possible on all operating systems.
# If running in a Windows environment this must be set to the same as your
# system time zone.
TIME_ZONE = 'UTC'

# Language code for this installation. All choices can be found here:
# http://www.w3.org/TR/REC-html40/struct/dirlang.html#langcodes
# http://blogs.law.harvard.edu/tech/stories/storyReader$15
LANGUAGE_CODE = 'en-us'

SITE_ID = 1

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = False

# Absolute path to the directory that holds media.
# Example: "/home/media/media.lawrence.com/"
MEDIA_ROOT = ''

# URL that handles the media served from MEDIA_ROOT.
# Example: "http://media.lawrence.com"
MEDIA_URL = ''

# URL prefix for static files.
STATIC_URL='/media/'

# Make this unique, and don't share it with anybody.
SECRET_KEY = 'pn-t15u(epetamdflb%dqaaxw+5u&2#0u-jah70w1l*_9*)=n7'

# List of callables that know how to import templates from various sources.
TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.Loader',
    'django.template.loaders.app_directories.Loader',
    #     'django.template.loaders.eggs.Loader',
)

MIDDLEWARE_CLASSES = (
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'autotest.frontend.apache_auth.ApacheAuthMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.middleware.doc.XViewMiddleware',
    'autotest.frontend.shared.json_html_formatter.JsonToHtmlMiddleware',
    'autotest.frontend.shared.retrieve_logs.RetrieveLogsHtmlMiddleware',
)

ROOT_URLCONF = 'autotest.frontend.urls'

TEMPLATE_DIRS = (
    # Put strings here, like "/home/html/django_templates" or "C:/www/django/templates".
    # Always use forward slashes, even on Windows.
    # Don't forget to use absolute paths, not relative paths.

    os.path.abspath(os.path.dirname(__file__) + '/templates')
)

INSTALLED_APPS = (
    'autotest.frontend.afe',
    'autotest.frontend.tko',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'south'
)

AUTHENTICATION_BACKENDS = (
    'autotest.frontend.apache_auth.SimpleAuthBackend',
)

# To prevent cache poisoning, please set this to the FQDN that your
# server will be responsible for
ALLOWED_HOSTS = ['*']
