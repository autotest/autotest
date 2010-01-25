import logging, pprint, re, urllib
import httplib2
from django.utils import simplejson


_RESOURCE_DIRECTORY_PATH = '/afe/server/resources/'


_http = httplib2.Http()


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
    def __init__(self, base_uri, representation_dict):
        self._base_uri = base_uri

        assert 'href' in representation_dict
        for key, value in representation_dict.iteritems():
            setattr(self, str(key), value)


    def __repr__(self):
        return 'Resource(%r)' % self._representation()


    def pprint(self):
        # pretty-print support for debugging/interactive use
        pprint.pprint(self._representation())


    @classmethod
    def directory(cls, base_uri):
        directory = cls(base_uri, {'href': _RESOURCE_DIRECTORY_PATH})
        return directory.get()


    def _read_representation(self, value):
        # recursively convert representation dicts to Resource objects
        if isinstance(value, list):
            return [self._read_representation(element) for element in value]
        if isinstance(value, dict):
            converted_dict = dict((key, self._read_representation(sub_value))
                                  for key, sub_value in value.iteritems())
            if 'href' in converted_dict:
                return type(self)(self._base_uri, converted_dict)
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


    def _request(self, method, query_parameters=None, encoded_body=None):
        uri_parts = []
        if not re.match(r'^https?://', self.href):
            uri_parts.append(self._base_uri)
        uri_parts.append(self.href)
        if query_parameters:
            query_string = urllib.urlencode(query_parameters)
            uri_parts.extend(['?', query_string])

        if encoded_body:
            entity_body = simplejson.dumps(encoded_body)
        else:
            entity_body = None

        full_uri = ''.join(uri_parts)
        logging.debug('%s %s', method, full_uri)
        if entity_body:
            logging.debug(entity_body)
        headers, response_body = _http.request(
                ''.join(uri_parts), method, body=entity_body,
                headers={'Content-Type': 'application/json'})
        logging.debug('Response: %s', headers['status'])

        response = Response(headers, response_body)
        if 300 <= response.status < 400: # redirection
            raise NotImplementedError(str(response)) # TODO
        if 400 <= response.status < 500:
            raise ClientError(str(response))
        if 500 <= response.status < 600:
            raise ServerError(str(response))
        return response


    def _stringify_query_parameter(self, value):
        if isinstance(value, (list, tuple)):
            return ','.join(value)
        return str(value)


    def get(self, **query_parameters):
        string_parameters = dict((key, self._stringify_query_parameter(value))
                                 for key, value in query_parameters.iteritems()
                                 if value is not None)
        response = self._request('GET', query_parameters=string_parameters)
        assert response.status == 200
        return self._read_representation(response.decoded_body())


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
