import os, sys

try:
   import autotest.common
except ImportError:
   frontend_dir = os.path.dirname(sys.modules[__name__].__file__)
   sys.path.insert(0, frontend_dir)
   import common
   sys.path.pop(0)

path_list = ['/usr/local/autotest/site-packages', '/usr/local/autotest',
            '/usr/lib/python2.7/site-packages/autotest',
            '/usr/lib/python2.6/site-packages/autotest',
            '/usr/lib/python2.5/site-packages/autotest',
            '/usr/lib/python2.4/site-packages/autotest']

for p in path_list:
   if os.path.isdir(p):
       sys.path.append(p)

os.environ['DJANGO_SETTINGS_MODULE'] = 'autotest.frontend.settings'

import django.core.handlers.wsgi

_application = django.core.handlers.wsgi.WSGIHandler()

def application(environ, start_response):
    environ['DJANGO_USE_POST_REWRITE'] = "yes"
    environ['PATH_INFO'] = environ['SCRIPT_NAME'] + environ['PATH_INFO']
    return _application(environ, start_response)
