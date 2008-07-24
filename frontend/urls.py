from django.conf.urls.defaults import *
from django.conf import settings

RE_PREFIX = '^' + settings.URL_PREFIX

handler500 = 'frontend.afe.views.handler500'

urlpatterns = patterns('',
    (RE_PREFIX + r'admin/', include('django.contrib.admin.urls')),
    (RE_PREFIX, include('frontend.afe.urls')),
)
