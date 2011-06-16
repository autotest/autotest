import os
from django.conf.urls import defaults
from django.conf import settings

# The next two lines enable the admin and load each admin.py file:
from django.contrib import admin
admin.autodiscover()

RE_PREFIX = '^' + settings.URL_PREFIX
TKO_RE_PREFIX = '^' + settings.TKO_URL_PREFIX

handler404 = 'django.views.defaults.page_not_found'
handler500 = 'frontend.afe.views.handler500'

urlpatterns = defaults.patterns(
        '',
        (RE_PREFIX + r'admin/', defaults.include(admin.site.urls)),
        (RE_PREFIX, defaults.include('frontend.afe.urls')),
        (TKO_RE_PREFIX, defaults.include('frontend.tko.urls')),
        (RE_PREFIX + r'static/(?P<path>.*)', 'django.views.static.serve',
         {'document_root': os.path.join(os.path.dirname(__file__), 'static')}),
    )

if os.path.exists(os.path.join(os.path.dirname(__file__),
                               'tko', 'site_urls.py')):
    urlpatterns += defaults.patterns(
            '', (TKO_RE_PREFIX, defaults.include('frontend.tko.site_urls')))

debug_patterns = defaults.patterns(
        '',
        # redirect /tko and /results to local apache server
        (r'^(?P<path>(tko|results)/.*)$',
         'frontend.afe.views.redirect_with_extra_data',
         {'url': 'http://%(server_name)s/%(path)s?%(getdata)s'}),
    )

if settings.DEBUG:
    urlpatterns += debug_patterns
