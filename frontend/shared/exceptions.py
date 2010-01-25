from django import http

class RequestError(Exception):
    """Signifies that an error response should be returned."""

    def __init__(self, code, entity_body=''):
        if not entity_body.endswith('\n'):
            entity_body += '\n'
        self.response = http.HttpResponse(entity_body, status=code)


class BadRequest(RequestError):
    """An error was found with the request, 400 Bad Request will be returned.

    The exception string should contain a description of the error.
    """

    def __init__(self, description):
        super(BadRequest, self).__init__(400, description)
