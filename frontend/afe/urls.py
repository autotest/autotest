from autotest.frontend import settings, urls_common
from autotest.frontend.afe import resources
from autotest.frontend.afe.feeds import feed
from django.conf.urls import defaults

feeds = {
    'jobs': feed.JobFeed
}

urlpatterns, debug_patterns = (
    urls_common.generate_patterns('autotest.frontend.afe', 'AfeClient'))

resource_patterns = defaults.patterns(
    '',
    (r'^/?$', resources.ResourceDirectory.dispatch_request),
    (r'^atomic_group_classes/?$',
     resources.AtomicGroupClassCollection.dispatch_request),
    (r'^atomic_group_classes/(?P<ag_name>.+?)/?$',
     resources.AtomicGroupClass.dispatch_request),
    (r'^atomic_taggings/?$',
     resources.AtomicLabelTaggingCollection.dispatch_request),
    (r'^atomic_taggings/(?P<ag_name>.+?),(?P<label_name>.+?)/?$',
     resources.AtomicLabelTagging.dispatch_request),
    (r'^labels/?$', resources.LabelCollection.dispatch_request),
    (r'^labels/(?P<label_name>.+?)/?$', resources.Label.dispatch_request),
    (r'^users/?$', resources.UserCollection.dispatch_request),
    (r'^users/(?P<username>[@\w]+)/?$', resources.User.dispatch_request),
    (r'^user_acls/?$',
     resources.UserAclMembershipCollection.dispatch_request),
    (r'^user_acls/(?P<username>.+?),(?P<acl_name>.+?)/?$',
     resources.UserAclMembership.dispatch_request),
    (r'^acls/?$', resources.AclCollection.dispatch_request),
    (r'^acls/(?P<acl_name>.+?)/?$', resources.Acl.dispatch_request),
    (r'^hosts/?$', resources.HostCollection.dispatch_request),
    (r'^hosts/(?P<hostname>.+?)/?$', resources.Host.dispatch_request),
    (r'^labelings/?$', resources.HostLabelingCollection.dispatch_request),
    (r'^labelings/(?P<hostname>.+?),(?P<label_name>.+?)/?$',
     resources.HostLabeling.dispatch_request),
    (r'^host_acls/?$',
     resources.HostAclMembershipCollection.dispatch_request),
    (r'^host_acls/(?P<hostname>.+?),(?P<acl_name>.+?)/?$',
     resources.HostAclMembership.dispatch_request),
    (r'^tests/?$', resources.TestCollection.dispatch_request),
    (r'^tests/(?P<test_name>.+?)/?$', resources.Test.dispatch_request),
    (r'^test_dependencies/?$',
     resources.TestDependencyCollection.dispatch_request),
    (r'^test_dependencies/(?P<test_name>.+?),(?P<label_name>.+?)/?$',
     resources.TestDependency.dispatch_request),
    (r'^execution_info/?$', resources.ExecutionInfo.dispatch_request),
    (r'^queue_entries_request/?$',
     resources.QueueEntriesRequest.dispatch_request),
    (r'^jobs/?$', resources.JobCollection.dispatch_request),
    (r'^jobs/(?P<job_id>\d+)/?$', resources.Job.dispatch_request),
    (r'^queue_entries/?$', resources.QueueEntryCollection.dispatch_request),
    (r'^queue_entries/(?P<queue_entry_id>\d+?)/?$',
     resources.QueueEntry.dispatch_request),
    (r'^health_tasks/?$', resources.HealthTaskCollection.dispatch_request),
    (r'^health_tasks/(?P<task_id>\d+)/?$',
     resources.HealthTask.dispatch_request),
)

urlpatterns += defaults.patterns(
    '', (r'^resources/', defaults.include(resource_patterns)))

# Job feeds
debug_patterns += defaults.patterns(
    '',
    (r'^model_doc/', 'autotest.frontend.afe.views.model_documentation'),
    (r'^feeds/(?P<url>.*)/$', 'autotest.frontend.afe.feeds.feed.feed_view',
     {'feed_dict': feeds})
)

if settings.DEBUG:
    urlpatterns += debug_patterns
