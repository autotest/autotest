from django.conf.urls.defaults import *
import common
from autotest_lib.frontend import settings, urls_common

pattern_list, debug_pattern_list = (
        urls_common.generate_patterns(django_name='new_tko.tko',
                                           gwt_name='TkoClient'))

pattern_list += [(r'^(?:|noauth/)jsonp_rpc/',
                  'new_tko.tko.views.handle_jsonp_rpc'),
                 (r'^(?:|noauth/)csv/', 'new_tko.tko.views.handle_csv'),
                 (r'^(?:|noauth/)plot/', 'new_tko.tko.views.handle_plot')]

if settings.DEBUG:
    pattern_list += debug_pattern_list

urlpatterns = patterns('', *pattern_list)
