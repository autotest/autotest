#!/usr/bin/python

import common
import operator, unittest
import simplejson
from autotest_lib.frontend import setup_django_environment
from autotest_lib.frontend import setup_test_environment
from django.test import client
from autotest_lib.frontend.afe import control_file, frontend_test_utils, models

class ResourceTestCase(unittest.TestCase,
                       frontend_test_utils.FrontendTestMixin):
    URI_PREFIX = '/afe/server/resources'

    CONTROL_FILE_CONTENTS = 'my control file contents'

    def setUp(self):
        super(ResourceTestCase, self).setUp()
        self._frontend_common_setup()
        self._setup_debug_user()
        self._add_additional_data()
        self.client = client.Client()


    def tearDown(self):
        super(ResourceTestCase, self).tearDown()
        self._frontend_common_teardown()


    def _setup_debug_user(self):
        user = models.User.objects.create(login='debug_user')
        acl = models.AclGroup.objects.get(name='my_acl')
        user.aclgroup_set.add(acl)


    def _add_additional_data(self):
        models.Test.objects.create(name='mytest',
                                   test_type=models.Test.Types.SERVER,
                                   path='/path/to/mytest')


    def _expected_status(self, method):
        if method == 'post':
            return 201
        if method == 'delete':
            return 204
        return 200


    def request(self, method, uri, **kwargs):
        expected_status = self._expected_status(method)

        if method == 'put':
            # the put() implementation in Django's test client is poorly
            # implemented and only supports url-encoded keyvals for the data.
            # the post() implementation is correct, though, so use that, with a
            # trick to override the method.
            method = 'post'
            kwargs['REQUEST_METHOD'] = 'PUT'
        if 'data' in kwargs:
            kwargs.setdefault('content_type', 'application/json')
            if kwargs['content_type'] == 'application/json':
                kwargs['data'] = simplejson.dumps(kwargs['data'])

        client_method = getattr(self.client, method)
        response = client_method(self.URI_PREFIX + '/' + uri, **kwargs)
        self.assertEquals(
                response.status_code, expected_status,
                'Expected %s, got %s: %s'
                % (expected_status, response.status_code, response.content))

        if response['content-type'] != 'application/json':
            return response.content

        try:
            return simplejson.loads(response.content)
        except ValueError:
            self.fail('Invalid reponse body: %s' % response.content)


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

        @param collection: an iterable of dicts
        @param attribute_or_list: an attribute or list of attributes to read.
                the results will be sorted and compared with expected_list. if
                a list of attributes is given, the attributes will be read
                hierarchically, i.e. item[attribute1][attribute2]...
        @param expected_list: list of expected values
        @param check_number: if given, only check this number of entries
        @param length: expected length of list, only necessary if check_number
                is given
        """
        actual_list = sorted(self._read_attribute(item, attribute_or_list)
                             for item in collection)
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


class FilteringPagingTest(ResourceTestCase):
    # we'll arbitarily choose to use hosts for this

    def setUp(self):
        super(FilteringPagingTest, self).setUp()

        self.labels[0].host_set = [self.hosts[0], self.hosts[1]]
        for host in self.hosts[:3]:
            host.locked = True
            host.save()

    def test_simple_filtering(self):
        response = self.request('get', 'hosts?locked=true&has_label=label1')
        self.check_collection(response['members'], 'hostname',
                              ['host1', 'host2'])


    def test_paging(self):
        response = self.request('get', 'hosts?start_index=1&items_per_page=2')
        self.check_collection(response['members'], 'hostname',
                              ['host2', 'host3'])
        self.assertEquals(response['total_results'], 9)
        self.assertEquals(response['items_per_page'], 2)
        self.assertEquals(response['start_index'], 1)


class AtomicGroupClassTest(ResourceTestCase):
    def test_collection(self):
        response = self.request('get', 'atomic_group_classes')
        self.check_collection(response['members'], 'name',
                              ['atomic1', 'atomic2'], length=2)


    def test_entry(self):
        response = self.request('get', 'atomic_group_classes/atomic1')
        self.assertEquals(response['name'], 'atomic1')
        self.assertEquals(response['max_number_of_machines'], 2)


    def test_labels(self):
        response = self.request('get', 'atomic_group_classes/atomic1/labels')
        self.check_collection(response['members'], 'name', ['label4', 'label5'])


class LabelTest(ResourceTestCase):
    def test_collection(self):
        response = self.request('get', 'labels')
        self.check_collection(response['members'], 'name', ['label1', 'label2'],
                              length=9, check_number=2)
        label1 = self.sorted_by(response['members'], 'name')[0]
        self.assertEquals(label1['is_platform'], False)


    def test_entry(self):
        response = self.request('get', 'labels/label1')
        self.assertEquals(response['name'], 'label1')
        self.assertEquals(response['is_platform'], False)
        self.assertEquals(response['atomic_group_class'], None)


    def test_hosts(self):
        response = self.request('get', 'labels/label1/hosts')
        self.assertEquals(len(response['members']), 1)
        self.check_collection(response['members'], 'hostname', ['host1'])


class UserTest(ResourceTestCase):
    def test_collection(self):
        response = self.request('get', 'users')
        self.check_collection(response['members'], 'username',
                              ['autotest_system', 'debug_user'])


    def test_entry(self):
        response = self.request('get', 'users/debug_user')
        self.assertEquals(response['username'], 'debug_user')

        me_response = self.request('get', 'users/@me')
        self.assertEquals(response, me_response)


    def test_acls(self):
        response = self.request('get', 'users/debug_user/acls')
        self.check_collection(response['members'], 'name',
                              ['Everyone', 'my_acl'])


    def test_accessible_hosts(self):
        group = models.AclGroup.objects.create(name='mygroup')
        models.User.objects.get(login='debug_user').aclgroup_set = [group]
        self.hosts[0].aclgroup_set = [group]

        response = self.request('get', 'users/debug_user/accessible_hosts')
        self.check_collection(response['members'], 'hostname', ['host1'])


class AclTest(ResourceTestCase):
    def test_collection(self):
        response = self.request('get', 'acls')
        self.check_collection(response['members'], 'name',
                              ['Everyone', 'my_acl'])


    def test_entry(self):
        response = self.request('get', 'acls/my_acl')
        self.assertEquals(response['name'], 'my_acl')


    def test_users(self):
        response = self.request('get', 'acls/my_acl/users')
        self.check_collection(response['members'], 'username',
                              ['autotest_system', 'debug_user'])


    def test_hosts(self):
        response = self.request('get', 'acls/my_acl/hosts')
        self.check_collection(response['members'], 'hostname',
                              ['host1', 'host2'], length=9, check_number=2)


class HostTest(ResourceTestCase):
    def test_collection(self):
        response = self.request('get', 'hosts')
        self.check_collection(response['members'], 'hostname',
                              ['host1', 'host2'], length=9, check_number=2)
        host1 = self.sorted_by(response['members'], 'hostname')[0]
        self.assertEquals(host1['platform']['name'], 'myplatform')
        self.assertEquals(host1['locked'], False)
        self.assertEquals(host1['status'], 'Ready')


    def test_entry(self):
        response = self.request('get', 'hosts/host1')
        self.assertEquals(response['protection_level'], 'No protection')


    def test_labels(self):
        response = self.request('get', 'hosts/host1/labels')
        self.check_collection(response['members'], 'name',
                              ['label1', 'myplatform'])


    def test_acls(self):
        response = self.request('get', 'hosts/host1/acls')
        self.check_collection(response['members'], 'name', ['my_acl'])


    def test_queue_entries(self):
        self._create_job(hosts=[1])
        response = self.request('get', 'hosts/host1/queue_entries')
        self.assertEquals(len(response['members']), 1)
        entry = response['members'][0]
        self.assertEquals(entry['job']['id'], 1)


    def test_health_tasks(self):
        models.SpecialTask.schedule_special_task(
                host=self.hosts[0], task=models.SpecialTask.Task.VERIFY)
        response = self.request('get', 'hosts/host1/health_tasks')
        self.check_collection(response['members'], 'task_type', ['Verify'])


    def test_put(self):
        response = self.request('put', 'hosts/host1', data={'locked': True})
        self.assertEquals(response['locked'], True)
        response = self.request('get', 'hosts/host1')
        self.assertEquals(response['locked'], True)
        self.assertEquals(response['locked_by']['username'], 'debug_user')


    def test_post(self):
        data = {'hostname': 'newhost',
                'acls': [self.URI_PREFIX + '/acls/my_acl'],
                'platform': {'href': self.URI_PREFIX + '/labels/myplatform'},
                'protection_level': 'Do not verify'}
        response = self.request('post', 'hosts', data=data)
        self.assertEquals(response, self.URI_PREFIX + '/hosts/newhost')

        host = models.Host.objects.get(hostname='newhost')
        self.assertEquals(host.platform().name, 'myplatform')
        self.assertEquals(host.protection, models.Host.Protection.DO_NOT_VERIFY)
        acls = host.aclgroup_set.all()
        self.assertEquals(len(acls), 1)
        self.assertEquals(acls[0].name, 'my_acl')


    def test_add_label(self):
        labels_response = self.request('get', 'hosts/host1/labels')
        labels_response['members'].append(
                {'href': self.URI_PREFIX + '/labels/label2'})
        response = self.request('put', 'hosts/host1/labels',
                                data=labels_response)
        self.check_collection(response['members'], 'name',
                              ['label1', 'label2', 'myplatform'])


    def test_delete(self):
        self.request('delete', 'hosts/host1')
        hosts = models.Host.valid_objects.filter(hostname='host1')
        self.assertEquals(len(hosts), 0)


class TestTest(ResourceTestCase): # yes, we're testing the "tests" resource
    def test_collection(self):
        response = self.request('get', 'tests')
        self.check_collection(response['members'], 'name', ['mytest'])


    def test_entry(self):
        response = self.request('get', 'tests/mytest')
        self.assertEquals(response['name'], 'mytest')
        self.assertEquals(response['control_file_type'], 'Server')
        self.assertEquals(response['control_file_path'], '/path/to/mytest')


    def test_dependencies(self):
        models.Test.objects.get(name='mytest').dependency_labels = [self.label3]
        response = self.request('get', 'tests/mytest/dependencies')
        self.check_collection(response['members'], 'name', ['label3'])


class ExecutionInfoTest(ResourceTestCase):
    def setUp(self):
        super(ExecutionInfoTest, self).setUp()

        def mock_read_control_file(test):
            return self.CONTROL_FILE_CONTENTS
        self.god.stub_with(control_file, 'read_control_file',
                           mock_read_control_file)
    def test_get(self):
        response = self.request('get', 'execution_info?tests=mytest')
        info = response['execution_info']
        self.assert_(self.CONTROL_FILE_CONTENTS in info['control_file'])
        self.assertEquals(info['is_server'], True)
        self.assertEquals(info['machines_per_execution'], 1)


class QueueEntriesRequestTest(ResourceTestCase):
    def test_get(self):
        response = self.request(
                'get',
                'queue_entries_request?hosts=host1,host2&meta_hosts=label1')

        # choose an arbitrary but consistent ordering to ease checking
        def entry_href(entry):
            if 'host' in entry:
                return entry['host']['href']
            return entry['meta_host']['href']
        entries = sorted(response['queue_entries'], key=entry_href)

        expected = [
                {'host': {'href': self.URI_PREFIX + '/hosts/host1'}},
                {'host': {'href': self.URI_PREFIX + '/hosts/host2'}},
                {'meta_host': {'href': self.URI_PREFIX + '/labels/label1'}}]
        self.assertEquals(entries, expected)


class JobTest(ResourceTestCase):
    def setUp(self):
        super(JobTest, self).setUp()

        for _ in xrange(2):
            self._create_job(hosts=[1, 2])

        job = models.Job.objects.get(id=1)
        job.control_file = self.CONTROL_FILE_CONTENTS
        job.save()


    def test_collection(self):
        response = self.request('get', 'jobs')
        self.check_collection(response['members'], 'id', [1, 2])


    def test_entry(self):
        response = self.request('get', 'jobs/1')
        self.assertEquals(response['id'], 1)
        self.assertEquals(response['name'], 'test')
        info = response['execution_info']
        self.assertEquals(info['control_file'], self.CONTROL_FILE_CONTENTS)
        self.assertEquals(info['is_server'], False)
        self.assertEquals(info['cleanup_before_job'], 'Never')
        self.assertEquals(info['cleanup_after_job'], 'Always')
        self.assertEquals(info['machines_per_execution'], 1)
        self.assertEquals(info['run_verify'], True)


    def test_queue_entries(self):
        response = self.request('get', 'jobs/1/queue_entries')
        self.check_collection(response['members'], ['host', 'hostname'],
                              ['host1', 'host2'])


    def test_post(self):
        data = {'name': 'myjob',
                'execution_info': {'control_file': self.CONTROL_FILE_CONTENTS,
                                   'is_server': True},
                'queue_entries':
                [{'host': {'href': self.URI_PREFIX + '/hosts/host1'}},
                 {'host': {'href': self.URI_PREFIX + '/hosts/host2'}}]}
        response = self.request('post', 'jobs', data=data)
        self.assertEquals(response, self.URI_PREFIX + '/jobs/3')
        job = models.Job.objects.get(id=3)
        self.assertEquals(job.name, 'myjob')
        self.assertEquals(job.control_file, self.CONTROL_FILE_CONTENTS)
        self.assertEquals(job.control_type, models.Job.ControlType.SERVER)
        entries = job.hostqueueentry_set.order_by('host__hostname')
        self.assertEquals(entries[0].host.hostname, 'host1')
        self.assertEquals(entries[1].host.hostname, 'host2')


class DirectoryTest(ResourceTestCase):
    def test_get(self):
        response = self.request('get', '')
        for key in ('atomic_group_classes', 'labels', 'users', 'acl_groups',
                    'hosts', 'tests', 'jobs', 'execution_info',
                    'queue_entries_request'):
            self.assert_(key in response)


if __name__ == '__main__':
    unittest.main()
