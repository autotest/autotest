from django.conf.urls import defaults
import common
from autotest_lib.frontend import settings, urls_common

urlpatterns, debug_patterns = (
        urls_common.generate_patterns('frontend.planner',
                                           'TestPlannerClient'))

if settings.DEBUG:
    urlpatterns += debug_patterns
