from django.conf.urls.defaults import *
from django.conf import settings
import os

RE_PREFIX = '^' + settings.URL_PREFIX

pattern_list = (
    (RE_PREFIX + r'admin/', include('django.contrib.admin.urls')),
    (RE_PREFIX, include('new_tko.tko.urls')),
)

if os.path.exists(os.path.join(os.path.dirname(__file__),
                               'tko', 'site_urls.py')):
    pattern_list += ((RE_PREFIX, include('new_tko.tko.site_urls')),)

debug_pattern_list = (
    # redirect /tko and /results to local apache server
    (r'^(?P<path>(tko|results)/.*)$',
     'frontend.afe.views.redirect_with_extra_data',
     {'url': 'http://%(server_name)s/%(path)s?%(getdata)s'}),
)

if settings.DEBUG:
  pattern_list += debug_pattern_list

urlpatterns = patterns('', *pattern_list)
