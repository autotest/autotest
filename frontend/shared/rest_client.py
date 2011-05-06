import copy, getpass, logging, pprint, re, urllib, urlparse
import httplib2
from django.utils import datastructures, simplejson
from autotest_lib.frontend.afe import rpc_client_lib
from autotest_lib.client.common_lib import utils


_request_headers = {}


def _get_request_headers(uri):
    server = urlparse.urlparse(uri)[0:2]
    if server in _request_headers:
        return _request_headers[server]

    headers = rpc_client_lib.authorization_headers(getpass.getuser(), uri)
    headers['Content-Type'] = 'application/json'

    _request_headers[server] = headers
    return headers


def _clear_request_headers(uri):
    server = urlparse.urlparse(uri)[0:2]
    if server in _request_headers:
        del _request_headers[server]


def _site_verify_response_default(headers, response_body):
    return headers['status'] != '401'


class RestClientError(Exception):
    pass


class ClientError(Exception):
    pass


class ServerError(Exception):
    pass


class Response(object):
    def __init__(self, httplib_response, httplib_content):
        self.status = int(httplib_response['status'])
        self.headers = httplib_response
        self.entity_body = httplib_content


    def decoded_body(self):
        return simplejson.loads(self.entity_body)


    def __str__(self):
        return '\n'.join([str(self.status), self.entity_body])


class Resource(object):
    def __init__(self, representation_dict, http):
        self._http = http
        assert 'href' in representation_dict
        for key, value in representation_dict.iteritems():
            setattr(self, str(key), value)


    def __repr__(self):
        return 'Resource(%r)' % self._representation()


    def pprint(self):
        # pretty-print support for debugging/interactive use
        pprint.pprint(self._representation())


    @classmethod
    def load(cls, uri, http=None):
        if not http:
            http = httplib2.Http()
        directory = cls({'href': uri}, http)
        return directory.get()


    def _read_representation(self, value):
        # recursively convert representation dicts to Resource objects
        if isinstance(value, list):
            return [self._read_representation(element) for element in value]
        if isinstance(value, dict):
            converted_dict = dict((key, self._read_representation(sub_value))
                                  for key, sub_value in value.iteritems())
            if 'href' in converted_dict:
                return type(self)(converted_dict, http=self._http)
            return converted_dict
        return value


    def _write_representation(self, value):
        # recursively convert Resource objects to representation dicts
        if isinstance(value, list):
            return [self._write_representation(element) for element in value]
        if isinstance(value, dict):
            return dict((key, self._write_representation(sub_value))
                        for key, sub_value in value.iteritems())
        if isinstance(value, Resource):
            return value._representation()
        return value


    def _representation(self):
        return dict((key, self._write_representation(value))
                    for key, value in self.__dict__.iteritems()
                    if not key.startswith('_')
                    and not callable(value))


    def _do_request(self, method, uri, query_parameters, encoded_body):
        uri_parts = [uri]
        if query_parameters:
            if '?' in uri:
                uri_parts += '&'
            else:
                uri_parts += '?'
            uri_parts += urllib.urlencode(query_parameters, doseq=True)
        full_uri = ''.join(uri_parts)

        if encoded_body:
            entity_body = simplejson.dumps(encoded_body)
        else:
            entity_body = None

        logging.debug('%s %s', method, full_uri)
        if entity_body:
            logging.debug(entity_body)

        site_verify = utils.import_site_function(
                __file__, 'autotest_lib.frontend.shared.site_rest_client',
                'site_verify_response', _site_verify_response_default)
        headers, response_body = self._http.request(
                full_uri, method, body=entity_body,
                headers=_get_request_headers(uri))
        if not site_verify(headers, response_body):
            logging.debug('Response verification failed, clearing headers and '
                          'trying again:\n%s', response_body)
            _clear_request_headers(uri)
            headers, response_body = self._http.request(
                full_uri, method, body=entity_body,
                headers=_get_request_headers(uri))

        logging.debug('Response: %s', headers['status'])

        return Response(headers, response_body)


    def _request(self, method, query_parameters=None, encoded_body=None):
        if query_parameters is None:
            query_parameters = {}

        response = self._do_request(method, self.href, query_parameters,
                                    encoded_body)

        if 300 <= response.status < 400: # redirection
            return self._do_request(method, response.headers['location'],
                                    query_parameters, encoded_body)
        if 400 <= response.status < 500:
            raise ClientError(str(response))
        if 500 <= response.status < 600:
            raise ServerError(str(response))
        return response


    def _stringify_query_parameter(self, value):
        if isinstance(value, (list, tuple)):
            return ','.join(self._stringify_query_parameter(item)
                            for item in value)
        return str(value)


    def _iterlists(self, mapping):
        """This effectively lets us treat dicts as MultiValueDicts."""
        if hasattr(mapping, 'iterlists'): # mapping is already a MultiValueDict
            return mapping.iterlists()
        return ((key, (value,)) for key, value in mapping.iteritems())


    def get(self, query_parameters=None, **kwarg_query_parameters):
        """
        @param query_parameters: a dict or MultiValueDict
        """
        query_parameters = copy.copy(query_parameters) # avoid mutating original
        if query_parameters is None:
            query_parameters = {}
        query_parameters.update(kwarg_query_parameters)

        string_parameters = datastructures.MultiValueDict()
        for key, values in self._iterlists(query_parameters):
            string_parameters.setlist(
                    key, [self._stringify_query_parameter(value)
                          for value in values])

        response = self._request('GET',
                                 query_parameters=string_parameters.lists())
        assert response.status == 200
        return self._read_representation(response.decoded_body())


    def get_full(self, results_limit, query_parameters=None,
                 **kwarg_query_parameters):
        """
        Like get() for collections, when the full collection is expected.

        @param results_limit: maxmimum number of results to allow
        @raises ClientError if there are more than results_limit results.
        """
        result = self.get(query_parameters=query_parameters,
                          items_per_page=results_limit,
                          **kwarg_query_parameters)
        if result.total_results > results_limit:
            raise ClientError(
                    'Too many results (%s > %s) for request %s (%s %s)'
                    % (result.total_results, results_limit, self.href,
                       query_parameters, kwarg_query_parameters))
        return result



    def put(self):
        response = self._request('PUT', encoded_body=self._representation())
        assert response.status == 200
        return self._read_representation(response.decoded_body())


    def delete(self):
        response = self._request('DELETE')
        assert response.status == 204 # no content


    def post(self, request_dict):
        # request_dict may still have resources in it
        request_dict = self._write_representation(request_dict)
        response = self._request('POST', encoded_body=request_dict)
        assert response.status == 201 # created
        return self._read_representation({'href': response.headers['location']})
