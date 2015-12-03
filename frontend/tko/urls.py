from django.conf.urls import defaults
try:
    import autotest.common as common  # pylint: disable=W0611
except ImportError:
    import common  # pylint: disable=W0611
from autotest.frontend import settings, urls_common
from autotest.frontend.tko import resources

urlpatterns, debug_patterns = (
    urls_common.generate_patterns('autotest.frontend.tko', 'TkoClient'))

resource_patterns = defaults.patterns(
    '',
    (r'^/?$', resources.ResourceDirectory.dispatch_request),
    (r'^test_results/?$', resources.TestResultCollection.dispatch_request),
    (r'^test_results/(?P<test_id>\d+)/?$',
     resources.TestResult.dispatch_request),
)

urlpatterns += defaults.patterns(
    '',
    (r'^jsonp_rpc/', 'autotest.frontend.tko.views.handle_jsonp_rpc'),
    (r'^csv/', 'autotest.frontend.tko.views.handle_csv'),
    (r'^plot/', 'autotest.frontend.tko.views.handle_plot'),

    (r'^resources/', defaults.include(resource_patterns)))

if settings.DEBUG:
    urlpatterns += debug_patterns
