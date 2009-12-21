from django.conf.urls.defaults import *
import common
from autotest_lib.frontend import settings, urls_common
from autotest_lib.frontend.afe.feeds import feed

feeds = {
    'jobs' : feed.JobFeed
}

pattern_list, debug_pattern_list = (
        urls_common.generate_pattern_lists('frontend.afe', 'AfeClient'))

# Job feeds
debug_pattern_list.append((
        r'^feeds/(?P<url>.*)/$', 'frontend.afe.feeds.feed.feed_view',
        {'feed_dict': feeds}))

if settings.DEBUG:
    pattern_list += debug_pattern_list

urlpatterns = patterns('', *pattern_list)
