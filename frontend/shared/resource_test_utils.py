import operator
import unittest
import simplejson
from django.test import client
from autotest.frontend import test_utils
from autotest.frontend.afe import models as afe_models


class ResourceTestCase(unittest.TestCase,
                       test_utils.FrontendTestMixin):
    URI_PREFIX = None  # subclasses may override this to use partial URIs

    def setUp(self):
        super(ResourceTestCase, self).setUp()
        self._frontend_common_setup()
        self._setup_debug_user()
        self.client = client.Client()

    def tearDown(self):
        super(ResourceTestCase, self).tearDown()
        self._frontend_common_teardown()

    def _setup_debug_user(self):
        user = afe_models.User.objects.create(login='debug_user')
        acl = afe_models.AclGroup.objects.get(name='my_acl')
        user.aclgroup_set.add(acl)

    def _expected_status(self, method):
        if method == 'post':
            return 201
        if method == 'delete':
            return 204
        return 200

    def raw_request(self, method, uri, **kwargs):
        method = method.lower()
        if method == 'put':
            # the put() implementation in Django's test client is poorly
            # implemented and only supports url-encoded keyvals for the data.
            # the post() implementation is correct, though, so use that, with a
            # trick to override the method.
            method = 'post'
            kwargs['REQUEST_METHOD'] = 'PUT'

        client_method = getattr(self.client, method)
        return client_method(uri, **kwargs)

    def request(self, method, uri, encode_body=True, **kwargs):
        expected_status = self._expected_status(method)

        if 'data' in kwargs:
            kwargs.setdefault('content_type', 'application/json')
            if kwargs['content_type'] == 'application/json':
                kwargs['data'] = simplejson.dumps(kwargs['data'])

        if uri.startswith('http://'):
            full_uri = uri
        else:
            assert self.URI_PREFIX
            full_uri = self.URI_PREFIX + '/' + uri

        response = self.raw_request(method, full_uri, **kwargs)
        self.assertEquals(
            response.status_code, expected_status,
            'Requesting %s\nExpected %s, got %s: %s (headers: %s)'
            % (full_uri, expected_status, response.status_code,
               response.content, response._headers))

        if response['content-type'] != 'application/json':
            return response.content

        try:
            return simplejson.loads(response.content)
        except ValueError:
            self.fail('Invalid response body: %s' % response.content)

    def sorted_by(self, collection, attribute):
        return sorted(collection, key=operator.itemgetter(attribute))

    def _read_attribute(self, item, attribute_or_list):
        if isinstance(attribute_or_list, basestring):
            attribute_or_list = [attribute_or_list]
        for attribute in attribute_or_list:
            item = item[attribute]
        return item

    def check_collection(self, collection, attribute_or_list, expected_list,
                         length=None, check_number=None):
        """Check the members of a collection of dicts.

        :param collection: an iterable of dicts
        :param attribute_or_list: an attribute or list of attributes to read.
                the results will be sorted and compared with expected_list. if
                a list of attributes is given, the attributes will be read
                hierarchically, i.e. item[attribute1][attribute2]...
        :param expected_list: list of expected values
        :param check_number: if given, only check this number of entries
        :param length: expected length of list, only necessary if check_number
                is given
        """
        actual_list = sorted(self._read_attribute(item, attribute_or_list)
                             for item in collection['members'])
        if length is None and check_number is None:
            length = len(expected_list)
        if length is not None:
            self.assertEquals(len(actual_list), length,
                              'Expected %s, got %s: %s'
                              % (length, len(actual_list),
                                 ', '.join(str(item) for item in actual_list)))
        if check_number:
            actual_list = actual_list[:check_number]
        self.assertEquals(actual_list, expected_list)

    def check_relationship(self, resource_uri, relationship_name,
                           other_entry_name, field, expected_values,
                           length=None, check_number=None):
        """Check the members of a relationship collection.

        :param resource_uri: URI of base resource
        :param relationship_name: name of relationship attribute on base
                resource
        :param other_entry_name: name of other entry in relationship
        :param field: name of field to grab on other entry
        :param expected values: list of expected values for the given field
        """
        response = self.request('get', resource_uri)
        relationship_uri = response[relationship_name]['href']
        relationships = self.request('get', relationship_uri)
        self.check_collection(relationships, [other_entry_name, field],
                              expected_values, length, check_number)
