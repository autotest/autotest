# Django settings for frontend project.

import os
try:
    import autotest.common as common
except ImportError:
    import common
from autotest.client.shared import global_config

c = global_config.global_config
_section = 'AUTOTEST_WEB'

DEBUG = c.get_config_value(_section, "sql_debug_mode", type=bool, default=False)
TEMPLATE_DEBUG = c.get_config_value(_section, "template_debug_mode", type=bool,
                                    default=False)

FULL_ADMIN = False

ADMINS = (
    # ('Your Name', 'your_email@domain.com'),
)

MANAGERS = ADMINS

def _get_config(config_key, default=None):
    return c.get_config_value(_section, config_key, default=default)

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

DATABASES = {'default': AUTOTEST_DEFAULT}

# prefix applied to all URLs - useful if requests are coming through apache,
# and you need this app to coexist with others
URL_PREFIX = 'afe/server/'
TKO_URL_PREFIX = 'new_tko/server/'

# Local time zone for this installation. Choices can be found here:
# http://www.postgresql.org/docs/8.1/static/datetime-keywords.html#DATETIME-TIMEZONE-SET-TABLE
# although not all variations may be possible on all operating systems.
# If running in a Windows environment this must be set to the same as your
# system time zone.
TIME_ZONE = 'America/Los_Angeles'

# Language code for this installation. All choices can be found here:
# http://www.w3.org/TR/REC-html40/struct/dirlang.html#langcodes
# http://blogs.law.harvard.edu/tech/stories/storyReader$15
LANGUAGE_CODE = 'en-us'

SITE_ID = 1

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

# Absolute path to the directory that holds media.
# Example: "/home/media/media.lawrence.com/"
MEDIA_ROOT = ''

# URL that handles the media served from MEDIA_ROOT.
# Example: "http://media.lawrence.com"
MEDIA_URL = ''

# URL prefix for admin media -- CSS, JavaScript and images. Make sure to use a
# trailing slash.
# Examples: "http://foo.com/media/", "/media/".
ADMIN_MEDIA_PREFIX = '/media/'

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
    'frontend.apache_auth.ApacheAuthMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.middleware.doc.XViewMiddleware',
    'frontend.shared.json_html_formatter.JsonToHtmlMiddleware',
)

ROOT_URLCONF = 'frontend.urls'

TEMPLATE_DIRS = (
    # Put strings here, like "/home/html/django_templates" or "C:/www/django/templates".
    # Always use forward slashes, even on Windows.
    # Don't forget to use absolute paths, not relative paths.

    os.path.abspath(os.path.dirname(__file__) + '/templates')
)

INSTALLED_APPS = (
    'frontend.afe',
    'frontend.tko',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
)

AUTHENTICATION_BACKENDS = (
    'frontend.apache_auth.SimpleAuthBackend',
)
