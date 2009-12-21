from django.conf.urls.defaults import *
import common
from autotest_lib.frontend import settings, urls_common

pattern_list, debug_pattern_list = (
        urls_common.generate_pattern_lists('frontend.planner',
                                           'TestPlannerClient'))

if settings.DEBUG:
    pattern_list += debug_pattern_list

urlpatterns = patterns('', *pattern_list)
