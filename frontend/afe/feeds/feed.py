import django.http
from django.contrib.syndication import feeds
from autotest_lib.frontend.afe import models


# Copied from django/contrib/syndication/views.py.  The default view doesn't
# give the feed any way to access the request object, and we need to access it
# to get the server hostname.  So we're forced to copy the code here and modify
# it to pass in the request.
from django.http import HttpResponse, Http404

# name changed from feed to feed_view
def feed_view(request, url, feed_dict=None):
    if not feed_dict:
        raise Http404, "No feeds are registered."

    try:
        slug, param = url.split('/', 1)
    except ValueError:
        slug, param = url, ''

    try:
        f = feed_dict[slug]
    except KeyError:
        raise Http404, "Slug %r isn't registered." % slug

    try:
        # this line is changed from the Django library version to pass
        # in request instead of request.path
        feedgen = f(slug, request).get_feed(param)
    except feeds.FeedDoesNotExist:
        raise Http404, "Invalid feed parameters. Slug %r is valid, but other parameters, or lack thereof, are not." % slug

    response = HttpResponse(mimetype=feedgen.mime_type)
    feedgen.write(response, 'utf-8')
    return response
# end copied code

class JobFeed(feeds.Feed):
    """\
    Common feed functionality.
    """
    link  =  "/results"
    title_template = "feeds/job_feed_title.html"
    description_template = "feeds/job_feed_description.html"

    NUM_ITEMS = 20

    def __init__(self, slug, request):
        super(JobFeed, self).__init__(slug, request.path)
        server_hostname = django.http.get_host(request)
        self.full_link = 'http://' + server_hostname + self.link

    def title(self, obj):
        return "Automated Test Framework %s Jobs" % obj.capitalize()

    def get_object(self, bits):
        # bits[0] should be a job status
        return bits[0]

    def items(self, obj):
        item_list = models.HostQueueEntry.objects.filter(
            status__iexact=obj).select_related()
        return item_list.order_by('-id')[:self.NUM_ITEMS]

    def item_link(self, obj):
        return  '%s/%s-%s' % (self.full_link, obj.job.id, obj.job.owner)
