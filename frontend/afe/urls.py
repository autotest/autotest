from django.conf.urls import defaults
from autotest_lib.frontend import settings, urls_common
from autotest_lib.frontend.afe.feeds import feed
from autotest_lib.frontend.afe import resources

feeds = {
    'jobs' : feed.JobFeed
}

urlpatterns, debug_patterns = (
        urls_common.generate_patterns('frontend.afe', 'AfeClient'))

resource_patterns = defaults.patterns(
        '',
        (r'^/?$', resources.ResourceDirectory.dispatch_request),
        (r'^atomic_group_classes/?$',
         resources.AtomicGroupClassCollection.dispatch_request),
        (r'^atomic_group_classes/(\w+)/?$',
         resources.AtomicGroupClass.dispatch_request),
        (r'^atomic_group_classes/(\w+)/labels/?$',
         resources.AtomicGroupLabels.dispatch_request),
        (r'^labels/?$', resources.LabelCollection.dispatch_request),
        (r'^labels/(\w+)/?$', resources.Label.dispatch_request),
        (r'^labels/(\w+)/hosts/?$', resources.LabelHosts.dispatch_request),
        (r'^users/?$', resources.UserCollection.dispatch_request),
        (r'^users/([@\w]+)/?$', resources.User.dispatch_request),
        (r'^users/([@\w]+)/acls/?$', resources.UserAcls.dispatch_request),
        (r'^users/([@\w]+)/accessible_hosts/?$',
         resources.UserAccessibleHosts.dispatch_request),
        (r'^acls/?$', resources.AclCollection.dispatch_request),
        (r'^acls/(\w+)/?$', resources.Acl.dispatch_request),
        (r'^acls/(\w+)/users/?$', resources.AclUsers.dispatch_request),
        (r'^acls/(\w+)/hosts/?$', resources.AclHosts.dispatch_request),
        (r'^hosts/?$', resources.HostCollection.dispatch_request),
        (r'^hosts/(\w+)/?$', resources.Host.dispatch_request),
        (r'^hosts/(\w+)/labels/?$', resources.HostLabels.dispatch_request),
        (r'^hosts/(\w+)/acls/?$', resources.HostAcls.dispatch_request),
        (r'^hosts/(\w+)/queue_entries/?$',
         resources.HostQueueEntries.dispatch_request),
        (r'^hosts/(\w+)/health_tasks/?$',
         resources.HostHealthTasks.dispatch_request),
        (r'^hosts/(\w+)/health_tasks/(\d+)/?$',
         resources.HealthTask.dispatch_request),
        (r'^tests/?$', resources.TestCollection.dispatch_request),
        (r'^tests/(\w+)/?$', resources.Test.dispatch_request),
        (r'^tests/(\w+)/dependencies/?$',
         resources.TestDependencies.dispatch_request),
        (r'^execution_info/?$', resources.ExecutionInfo.dispatch_request),
        (r'^queue_entries_request/?$',
         resources.QueueEntriesRequest.dispatch_request),
        (r'^jobs/?$', resources.JobCollection.dispatch_request),
        (r'^jobs/(\d+)/?$', resources.Job.dispatch_request),
        (r'^jobs/(\d+)/queue_entries/?$',
         resources.JobQueueEntries.dispatch_request),
        (r'^jobs/(\d+)/queue_entries/(\d+)/?$',
         resources.QueueEntry.dispatch_request),
    )

urlpatterns += defaults.patterns(
        '', (r'^resources/', defaults.include(resource_patterns)))

# Job feeds
debug_patterns += defaults.patterns(
        '',
        (r'^model_doc/', 'frontend.afe.views.model_documentation'),
        (r'^feeds/(?P<url>.*)/$', 'frontend.afe.feeds.feed.feed_view',
         {'feed_dict': feeds})
    )

if True or settings.DEBUG:
    urlpatterns += debug_patterns
