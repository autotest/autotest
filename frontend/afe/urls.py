from django.conf.urls import defaults
import common
from autotest_lib.frontend import settings, urls_common
from autotest_lib.frontend.afe.feeds import feed

feeds = {
    'jobs' : feed.JobFeed
}

urlpatterns, debug_patterns = (
        urls_common.generate_patterns('frontend.afe', 'AfeClient'))

# Job feeds
debug_patterns += defaults.patterns(
        '',
        (r'^feeds/(?P<url>.*)/$', 'frontend.afe.feeds.feed.feed_view',
         {'feed_dict': feeds})
    )

if settings.DEBUG:
    urlpatterns += debug_patterns
