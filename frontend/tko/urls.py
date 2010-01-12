from django.conf.urls import defaults
import common
from autotest_lib.frontend import settings, urls_common

urlpatterns, debug_patterns = (
        urls_common.generate_patterns('frontend.tko', 'TkoClient'))

urlpatterns += defaults.patterns(
        '',
        (r'^(?:|noauth/)jsonp_rpc/', 'frontend.tko.views.handle_jsonp_rpc'),
        (r'^(?:|noauth/)csv/', 'frontend.tko.views.handle_csv'),
        (r'^(?:|noauth/)plot/', 'frontend.tko.views.handle_plot'))

if settings.DEBUG:
    urlpatterns += debug_patterns
