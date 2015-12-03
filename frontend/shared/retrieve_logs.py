from autotest.tko.retrieve_logs import retrieve_logs
from django.http import HttpResponsePermanentRedirect


class RetrieveLogsHtmlMiddleware(object):

    def process_response(self, request, response):
        if request.path.startswith('/retrieve_logs/'):
            job = request.GET.get('job', None)
            if job is not None:
                redirect_url = retrieve_logs(job)
                return HttpResponsePermanentRedirect(redirect_url)
        return response
