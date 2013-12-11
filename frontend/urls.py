import os
try:
    import autotest.common as common
except ImportError:
    import common
from autotest.shared import rpc
from autotest.shared import frontend
from django.conf.urls import defaults
from django.conf import settings

# The next two lines enable the admin and load each admin.py file:
from django.contrib import admin
admin.autodiscover()

# Prefixes as regexes, ready to be consumed by django's url dispatch mechanism
AFE_RE_PREFIX = '^%s' % frontend.AFE_URL_PREFIX
AFE_RE_ADMIN_PREFIX = '%sadmin/' % AFE_RE_PREFIX
AFE_RE_STATIC_PREFIX = '%sstatic/(?P<path>.*)' % AFE_RE_PREFIX
TKO_RE_PREFIX = '^%s' % frontend.TKO_URL_PREFIX

urlpatterns = defaults.patterns(
    '',
    (AFE_RE_ADMIN_PREFIX, defaults.include(admin.site.urls)),
    (AFE_RE_PREFIX, defaults.include('autotest.frontend.afe.urls')),
    (AFE_RE_STATIC_PREFIX, 'django.views.static.serve',
     {'document_root': os.path.join(os.path.dirname(__file__), 'static')}),
    (TKO_RE_PREFIX, defaults.include('autotest.frontend.tko.urls'))
)

handler404 = 'django.views.defaults.page_not_found'
handler500 = 'autotest.frontend.afe.views.handler500'

if os.path.exists(os.path.join(os.path.dirname(__file__),
                               'tko', 'site_urls.py')):
    urlpatterns += defaults.patterns(
        '', (TKO_RE_PREFIX, defaults.include('autotest.frontend.tko.site_urls')))

debug_patterns = defaults.patterns(
    '',
    # redirect /tko and /results to local apache server
    (r'^(?P<path>(tko|results)/.*)$',
     'autotest.frontend.afe.views.redirect_with_extra_data',
     {'url': 'http://%(server_name)s/%(path)s?%(getdata)s'}),
)

if settings.DEBUG:
    urlpatterns += debug_patterns
