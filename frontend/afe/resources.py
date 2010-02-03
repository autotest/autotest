from django import http
from autotest_lib.frontend.shared import query_lib, resource_lib
from autotest_lib.frontend.afe import control_file, models, rpc_utils
from autotest_lib.frontend import thread_local
from autotest_lib.client.common_lib import host_protections

class EntryWithInvalid(resource_lib.Entry):
    def put(self):
        if self.instance.invalid:
            raise http.Http404('%s has been deleted' % self.instance)
        return super(EntryWithInvalid, self).put()


    def delete(self):
        if self.instance.invalid:
            raise http.Http404('%s has already been deleted' % self.instance)
        return super(EntryWithInvalid, self).delete()


class AtomicGroupClass(EntryWithInvalid):
    @classmethod
    def from_uri_args(cls, request, name):
        return cls(request, models.AtomicGroup.objects.get(name=name))


    def _uri_args(self):
        return (self.instance.name,), {}


    def short_representation(self):
        rep = super(AtomicGroupClass, self).short_representation()
        rep['name'] = self.instance.name
        return rep


    def full_representation(self):
        rep = super(AtomicGroupClass, self).full_representation()
        rep.update({'max_number_of_machines':
                    self.instance.max_number_of_machines,
                    'labels': AtomicGroupLabels(self).link()})
        return rep


    @classmethod
    def create_instance(cls, input_dict, containing_collection):
        cls._check_for_required_fields(input_dict, ('name',))
        return models.AtomicGroup.add_object(name=input_dict['name'])


    def update(self, input_dict):
        data = {'max_number_of_machines':
                input_dict.get('max_number_of_machines')}
        data = input_dict.remove_unspecified_fields(data)
        self.instance.update_object(**data)


class AtomicGroupClassCollection(resource_lib.Collection):
    queryset = models.AtomicGroup.valid_objects.all()
    entry_class = AtomicGroupClass


class AtomicGroupLabels(resource_lib.Relationship):
    base_entry_class = AtomicGroupClass
    entry_class = 'autotest_lib.frontend.afe.resources.Label'

    def _fresh_queryset(self):
        return self.base_entry.instance.label_set.all()


    def _update_relationship(self, related_instances):
        self.base_entry.instance.label_set = related_instances


class Label(EntryWithInvalid):
    class QueryProcessor(query_lib.BaseQueryProcessor):
        @classmethod
        def _add_all_selectors(cls):
            cls._add_field_selector('name')
            cls._add_field_selector('is_platform', field='platform',
                                    value_transform=cls.read_boolean)


    @classmethod
    def from_uri_args(cls, request, name):
        return cls(request, models.Label.objects.get(name=name))


    def _uri_args(self):
        return (self.instance.name,), {}


    def short_representation(self):
        rep = super(Label, self).short_representation()
        rep.update({'name': self.instance.name,
                    'is_platform': bool(self.instance.platform)})
        return rep


    def full_representation(self):
        rep = super(Label, self).full_representation()
        atomic_group_class = AtomicGroupClass.from_optional_instance(
                self._request, self.instance.atomic_group)
        rep.update({'atomic_group_class':
                        atomic_group_class.short_representation(),
                    'hosts': LabelHosts(self).link()})
        return rep


    @classmethod
    def create_instance(cls, input_dict, containing_collection):
        cls._check_for_required_fields(input_dict, ('name',))
        return models.Label.add_object(name=input_dict['name'])


    def update(self, input_dict):
        # TODO update atomic group
        raise NotImplementedError


class LabelCollection(resource_lib.Collection):
    queryset = models.Label.valid_objects.all()
    entry_class = Label


class LabelHosts(resource_lib.Relationship):
    base_entry_class = Label
    entry_class = 'autotest_lib.frontend.afe.resources.Host'


    def _fresh_queryset(self):
        return self.base_entry.instance.host_set.all()


    def _update_relationship(self, related_instances):
        self.base_entry.instance.host_set = related_instances


class User(resource_lib.Entry):
    _permitted_methods = ('GET,')


    @classmethod
    def from_uri_args(cls, request, username):
        if username == '@me':
            username = models.User.current_user().login
        return cls(request, models.User.objects.get(login=username))


    def _uri_args(self):
        return (self.instance.login,), {}


    def short_representation(self):
        rep = super(User, self).short_representation()
        rep['username'] = self.instance.login
        return rep


    def full_representation(self):
        rep = super(User, self).full_representation()
        rep.update({'jobs': 'TODO',
                    'recurring_runs': 'TODO',
                    'accessible_hosts': UserAccessibleHosts(self).link(),
                    'acls': UserAcls(self).link()})
        return rep


class UserCollection(resource_lib.Collection):
    _permitted_methods = ('GET',)
    queryset = models.User.objects.all()
    entry_class = User


class UserAcls(resource_lib.Relationship):
    base_entry_class = User
    entry_class = 'autotest_lib.frontend.afe.resources.Acl'


    def _fresh_queryset(self):
        return self.base_entry.instance.aclgroup_set.all()


    def _update_relationship(self, related_instances):
        # TODO check for and add/remove "everyone"
        self.base_entry.instance.aclgroup_set = related_instances


class UserAccessibleHosts(resource_lib.Relationship):
    _permitted_methods = ('GET',)
    base_entry_class = User
    entry_class = 'autotest_lib.frontend.afe.resources.Host'


    def _fresh_queryset(self):
        return models.Host.objects.filter(
                aclgroup__users=self.base_entry.instance)


class Acl(resource_lib.Entry):
    _permitted_methods = ('GET',)

    @classmethod
    def from_uri_args(cls, request, name):
        return cls(request, models.AclGroup.objects.get(name=name))


    def _uri_args(self):
        return (self.instance.name,), {}


    def short_representation(self):
        rep = super(Acl, self).short_representation()
        rep['name'] = self.instance.name
        return rep


    def full_representation(self):
        rep = super(Acl, self).full_representation()
        rep.update({'users': AclUsers(self).link(),
                    'hosts': AclHosts(self).link()})
        return rep


    @classmethod
    def create_instance(cls, input_dict, containing_collection):
        cls._check_for_required_fields(input_dict, ('name',))
        return models.AclGroup.add_object(name=input_dict['name'])


    def update(self, input_dict):
        pass


class AclCollection(resource_lib.Collection):
    queryset = models.AclGroup.objects.all()
    entry_class = Acl


class AclUsers(resource_lib.Relationship):
    base_entry_class = Acl
    entry_class = User


    def _fresh_queryset(self):
        return self.base_entry.instance.users.all()


    def _update_relationship(self, related_instances):
        self.base_entry.instance.users = related_instances


class AclHosts(resource_lib.Relationship):
    base_entry_class = Acl
    entry_class = 'autotest_lib.frontend.afe.resources.Host'


    def _fresh_queryset(self):
        return self.base_entry.instance.hosts.all()


    def _update_relationship(self, related_instances):
        self.base_entry.instance.hosts = related_instances


class Host(EntryWithInvalid):
    class QueryProcessor(query_lib.BaseQueryProcessor):
        @classmethod
        def _add_all_selectors(cls):
            cls._add_field_selector('hostname')
            cls._add_field_selector('locked', value_transform=cls.read_boolean)
            cls._add_field_selector(
                'locked_by', field='locked_by__login',
                doc='Username of user who locked this host, if locked')
            cls._add_field_selector('status')
            cls._add_field_selector('protection_level', field='protection',
                                    doc='Verify/repair protection level',
                                    value_transform=Host._read_protection)
            cls._add_related_existence_selector('has_label', models.Label,
                                                'name')


    @classmethod
    def _read_protection(cls, protection_input):
        return host_protections.Protection.get_value(protection_input)


    @classmethod
    def from_uri_args(cls, request, hostname):
        return cls(request, models.Host.objects.get(hostname=hostname))


    def _uri_args(self):
        return (self.instance.hostname,), {}


    def short_representation(self):
        rep = super(Host, self).short_representation()
        # TODO calling platform() over and over is inefficient
        platform_rep = (Label.from_optional_instance(self._request,
                                                     self.instance.platform())
                        .short_representation())
        rep.update({'hostname': self.instance.hostname,
                    'locked': bool(self.instance.locked),
                    'status': self.instance.status,
                    'platform': platform_rep})
        return rep


    def full_representation(self):
        rep = super(Host, self).full_representation()
        protection = host_protections.Protection.get_string(
                self.instance.protection)
        locked_by = (User.from_optional_instance(self._request,
                                                 self.instance.locked_by)
                     .short_representation())
        rep.update({'locked_by': locked_by,
                    'locked_on': self._format_datetime(self.instance.lock_time),
                    'invalid': self.instance.invalid,
                    'protection_level': protection,
                    # TODO make these efficient
                    'labels': HostLabels(self).full_representation(),
                    'acls': HostAcls(self).full_representation(),
                    'queue_entries': HostQueueEntries(self).link(),
                    'health_tasks': HostHealthTasks(self).link()})
        return rep


    @classmethod
    def create_instance(cls, input_dict, containing_collection):
        cls._check_for_required_fields(input_dict, ('hostname',))

        # always create locked, so we can set up ACLs safely
        instance = models.Host.add_object(hostname=input_dict['hostname'],
                                          locked=True)

        if 'acls' in input_dict:
            entry = Host(containing_collection._request, instance)
            HostAcls(entry).update(input_dict['acls'])

        instance.locked = False # restore default
        instance.save()
        return instance


    def update(self, input_dict):
        data = {'locked': input_dict.get('locked'),
                'protection': input_dict.get('protection_level')}
        data = input_dict.remove_unspecified_fields(data)

        if 'protection' in data:
            data['protection'] = self._read_protection(data['protection'])

        self.instance.update_object(**data)

        if 'platform' in input_dict:
            label = self.resolve_link(input_dict['platform']) .instance
            if not label.platform:
                raise BadRequest('Label %s is not a platform' % label.name)
            for label in self.instance.labels.filter(platform=True):
                self.instance.labels.remove(label)
            self.instance.labels.add(label)


class HostCollection(resource_lib.Collection):
    queryset = models.Host.valid_objects.all()
    entry_class = Host


class HostLabels(resource_lib.Relationship):
    base_entry_class = Host
    entry_class = Label


    def _fresh_queryset(self):
        return self.base_entry.instance.labels.all()


    def _update_relationship(self, related_instances):
        self.base_entry.instance.labels = related_instances


class HostAcls(resource_lib.Relationship):
    base_entry_class = Host
    entry_class = Acl


    def _fresh_queryset(self):
        return self.base_entry.instance.aclgroup_set.all()


    def _update_relationship(self, related_instances):
        for acl in related_instances:
            acl.check_for_acl_violation_acl_group()
        self.base_entry.instance.aclgroup_set = related_instances
        models.AclGroup.on_host_membership_change()


class HostQueueEntries(resource_lib.Relationship):
    _permitted_methods = ('GET',)
    base_entry_class = Host
    entry_class = 'autotest_lib.frontend.afe.resources.QueueEntry'


    def _fresh_queryset(self):
        return self.base_entry.instance.hostqueueentry_set.order_by('-id')


class HostHealthTasks(resource_lib.Relationship):
    _permitted_methods = ('GET', 'POST')
    base_entry_class = Host
    entry_class = 'autotest_lib.frontend.afe.resources.HealthTask'


    def _fresh_queryset(self):
        return self.base_entry.instance.specialtask_set.order_by('-id')


class Test(resource_lib.Entry):
    @classmethod
    def from_uri_args(cls, request, name):
        return cls(request, models.Test.objects.get(name=name))


    def _uri_args(self):
        return (self.instance.name,), {}


    def short_representation(self):
        rep = super(Test, self).short_representation()
        rep['name'] = self.instance.name
        return rep


    def full_representation(self):
        rep = super(Test, self).full_representation()
        rep.update({'author': self.instance.author,
                    'class': self.instance.test_class,
                    'control_file_type':
                    models.Test.Types.get_string(self.instance.test_type),
                    'control_file_path': self.instance.path,
                    'dependencies': TestDependencies(self).link(),
                    })
        return rep


    @classmethod
    def create_instance(cls, input_dict, containing_collection):
        cls._check_for_required_fields(input_dict,
                                       ('name', 'control_file_type',
                                        'control_file_path'))
        test_type = models.Test.Type.get_value(input['control_file_type'])
        return models.Test.add_object(name=input_dict['name'],
                                      test_type=test_type,
                                      path=input_dict['control_file_path'])


    def update(self, input_dict):
        data = {'test_type': input_dict.get('control_file_type'),
                'path': input_dict.get('control_file_path'),
                'class': input_dict.get('class'),
                }
        data = input_dict.remove_unspecified_fields(data)
        self.instance.update_object(**data)


class TestCollection(resource_lib.Collection):
    queryset = models.Test.objects.all()
    entry_class = Test


class TestDependencies(resource_lib.Relationship):
    base_entry_class = Test
    entry_class = Label

    def _fresh_queryset(self):
        return self.base_entry.instance.dependency_labels.all()


    def _update_relationship(self, related_instances):
        self.base_entry.instance.dependency_labels = related_instances


# TODO profilers


class ExecutionInfo(resource_lib.Resource):
    _permitted_methods = ('GET','POST')
    _job_fields = models.Job.get_field_dict()
    _DEFAULTS = {
            'control_file': '',
            'is_server': True,
            'dependencies': [],
            'machines_per_execution': 1,
            'run_verify': bool(_job_fields['run_verify'].default),
            'timeout_hrs': _job_fields['timeout'].default,
            'maximum_runtime_hrs': _job_fields['max_runtime_hrs'].default,
            'cleanup_before_job':
                models.RebootBefore.get_string(models.DEFAULT_REBOOT_BEFORE),
            'cleanup_after_job':
                models.RebootAfter.get_string(models.DEFAULT_REBOOT_AFTER),
            }


    def _query_parameters(self):
        return (('tests', 'Comma-separated list of test names to run'),
                ('kernels', 'TODO'),
                ('client_control_file',
                 'Client control file segment to run after all specified '
                 'tests'),
                ('profilers',
                 'Comma-separated list of profilers to activate during the '
                 'job'),
                ('use_container', 'TODO'),
                ('profile_only',
                 'If true, run only profiled iterations; otherwise, always run '
                 'at least one non-profiled iteration in addition to a '
                 'profiled iteration'),
                ('upload_kernel_config',
                 'If true, generate a server control file code that uploads '
                 'the kernel config file to the client and tells the client of '
                 'the new (local) path when compiling the kernel; the tests '
                 'must be server side tests'))


    @classmethod
    def execution_info_from_job(cls, job):
        return {'control_file': job.control_file,
                'is_server': job.control_type == models.Job.ControlType.SERVER,
                'dependencies': [label.name for label
                                 in job.dependency_labels.all()],
                'machines_per_execution': job.synch_count,
                'run_verify': bool(job.run_verify),
                'timeout_hrs': job.timeout,
                'maximum_runtime_hrs': job.max_runtime_hrs,
                'cleanup_before_job':
                    models.RebootBefore.get_string(job.reboot_before),
                'cleanup_after_job':
                    models.RebootAfter.get_string(job.reboot_after),
                }


    def _get_execution_info(self, input_dict):
        tests = input_dict.get('tests', '')
        client_control_file = input_dict.get('client_control_file', None)
        if not tests and not client_control_file:
            return self._DEFAULTS

        test_list = tests.split(',')
        if 'profilers' in input_dict:
            profilers_list = input_dict['profilers'].split(',')
        else:
            profilers_list = []
        kernels = input_dict.get('kernels', '') # TODO
        if kernels:
            kernels = [dict(version=kernel) for kernel in kernels.split(',')]

        cf_info, test_objects, profiler_objects, label = (
                rpc_utils.prepare_generate_control_file(
                        test_list, kernels, None, profilers_list))
        control_file_contents = control_file.generate_control(
                tests=test_objects, kernels=kernels,
                profilers=profiler_objects, is_server=cf_info['is_server'],
                client_control_file=client_control_file,
                profile_only=input_dict.get('profile_only', None),
                upload_kernel_config=input_dict.get(
                    'upload_kernel_config', None))
        return dict(self._DEFAULTS,
                    control_file=control_file_contents,
                    is_server=cf_info['is_server'],
                    dependencies=cf_info['dependencies'],
                    machines_per_execution=cf_info['synch_count'])


    def handle_request(self):
        result = self.link()
        result['execution_info'] = self._get_execution_info(
                self._request.REQUEST)
        return self._basic_response(result)


class QueueEntriesRequest(resource_lib.Resource):
    _permitted_methods = ('GET',)


    def _query_parameters(self):
        return (('hosts', 'Comma-separated list of hostnames'),
                ('one_time_hosts',
                 'Comma-separated list of hostnames not already in the '
                 'Autotest system'),
                ('meta_hosts',
                 'Comma-separated list of label names; for each one, an entry '
                 'will be created and assigned at runtime to an available host '
                 'with that label'),
                ('atomic_group_class', 'TODO'))


    def _read_list(self, list_string):
        if list_string:
            return list_string.split(',')
        return []


    def handle_request(self):
        request_dict = self._request.REQUEST
        hosts = self._read_list(request_dict.get('hosts'))
        one_time_hosts = self._read_list(request_dict.get('one_time_hosts'))
        meta_hosts = self._read_list(request_dict.get('meta_hosts'))
        atomic_group_class = request_dict.get('atomic_group_class')

        # TODO: bring in all the atomic groups magic from create_job()

        entries = []
        for hostname in one_time_hosts:
            models.Host.create_one_time_host(hostname)
        for hostname in hosts:
            entry = Host.from_uri_args(self._request, hostname)
            entries.append({'host': entry.link()})
        for label_name in meta_hosts:
            entry = Label.from_uri_args(self._request, label_name)
            entries.append({'meta_host': entry.link()})

        result = self.link()
        result['queue_entries'] = entries
        return self._basic_response(result)


class Job(resource_lib.Entry):
    _permitted_methods = ('GET',)

    class _StatusConstraint(query_lib.Constraint):
        @classmethod
        def apply_constraint(cls, queryset, value, comparison_type, is_inverse):
            if comparison_type != 'equals' or is_inverse:
                raise query_lib.ConstraintError('Can only use this selector '
                                                'with equals')
            non_queued_statuses = [
                    status for status, _
                    in models.HostQueueEntry.Status.choices()
                    if status != models.HostQueueEntry.Status.QUEUED]
            if value == 'queued':
                return queryset.exclude(
                        hostqueueentry__status__in=non_queued_statuses)
            elif value == 'active':
                return queryset.filter(
                        hostqueueentry__status__in=non_queued_statuses).filter(
                        hostqueueentry__complete=False).distinct()
            elif value == 'complete':
                return queryset.exclude(hostqueueentry__complete=False)
            else:
                raise query_lib.ConstraintError('Value must be one of queued, '
                                                'active or complete')


    class QueryProcessor(query_lib.BaseQueryProcessor):
        @classmethod
        def _add_all_selectors(cls):
            cls._add_field_selector('id')
            cls._add_selector(
                    query_lib.Selector('status',
                                       doc='One of queued, active or complete'),
                    Job._StatusConstraint())


    @classmethod
    def from_uri_args(cls, request, job_id):
        return cls(request, models.Job.objects.get(id=job_id))


    def _uri_args(self):
        return (self.instance.id,), {}


    def short_representation(self):
        rep = super(Job, self).short_representation()
        rep.update({'id': self.instance.id,
                    'owner': self.instance.owner,
                    'name': self.instance.name,
                    'priority':
                        models.Job.Priority.get_string(self.instance.priority),
                    'created_on':
                        self._format_datetime(self.instance.created_on),
                    })
        return rep


    def full_representation(self):
        rep = super(Job, self).full_representation()
        rep.update({'email_list': self.instance.email_list,
                    'parse_failed_repair':
                        bool(self.instance.parse_failed_repair),
                    'execution_info':
                        ExecutionInfo.execution_info_from_job(self.instance),
                    'queue_entries': JobQueueEntries(self).link(),
                    })
        return rep


    @classmethod
    def create_instance(cls, input_dict, containing_collection):
        cls._check_for_required_fields(input_dict, ('name', 'execution_info',
                                                    'queue_entries'))
        execution_info = input_dict['execution_info']
        cls._check_for_required_fields(execution_info, ('control_file',
                                                        'is_server'))

        if execution_info['is_server']:
            control_type = models.Job.ControlType.SERVER
        else:
            control_type = models.Job.ControlType.CLIENT
        options = dict(
                name=input_dict['name'],
                priority=input_dict.get('priority', None),
                control_file=execution_info['control_file'],
                control_type=control_type,
                is_template=input_dict.get('is_template', None),
                timeout=execution_info.get('timeout_hrs'),
                max_runtime_hrs=execution_info.get('maximum_runtime_hrs'),
                synch_count=execution_info.get('machines_per_execution'),
                run_verify=execution_info.get('run_verify'),
                email_list=input_dict.get('email_list', None),
                dependencies=execution_info.get('dependencies', ()),
                reboot_before=execution_info.get('cleanup_before_job'),
                reboot_after=execution_info.get('cleanup_after_job'),
                parse_failed_repair=input_dict.get('parse_failed_repair', None),
                keyvals=input_dict.get('keyvals', None))

        host_objects, metahost_label_objects, atomic_group = [], [], None
        for queue_entry in input_dict['queue_entries']:
            if 'host' in queue_entry:
                host = queue_entry['host']
                if host: # can be None, indicated a hostless job
                    host_entry = containing_collection.resolve_link(host)
                    host_objects.append(host_entry.instance)
            elif 'meta_host' in queue_entry:
                label_entry = containing_collection.resolve_link(
                        queue_entry['meta_host'])
                metahost_label_objects.append(label_entry.instance)
            if 'atomic_group' in queue_entry:
                atomic_group_entry = containing_collection.resolve_link(
                        queue_entry['atomic_group'])
                if atomic_group:
                    assert atomic_group_entry.instance.id == atomic_group.id
                else:
                    atomic_group = atomic_group_entry.instance

        job_id = rpc_utils.create_new_job(
                owner=models.User.current_user().login,
                options=options,
                host_objects=host_objects,
                metahost_objects=metahost_label_objects,
                atomic_group=atomic_group)
        return models.Job.objects.get(id=job_id)


    def update(self, input_dict):
        # Required for POST, doesn't actually support PUT
        pass


class JobCollection(resource_lib.Collection):
    queryset = models.Job.objects.order_by('-id')
    entry_class = Job


class JobQueueEntries(resource_lib.Relationship):
    _permitted_methods = ('GET',)

    base_entry_class = Job
    entry_class = 'autotest_lib.frontend.afe.resources.QueueEntry'

    def _fresh_queryset(self):
        return self.base_entry.instance.hostqueueentry_set.all()


class QueueEntry(resource_lib.Entry):
    _permitted_methods = ('GET', 'PUT')

    @classmethod
    def from_uri_args(cls, request, job_id, queue_entry_id):
        instance = models.HostQueueEntry.objects.get(id=queue_entry_id)
        if instance.job.id != int(job_id):
            raise http.Http404('Incorrect job ID %r (expected %r)'
                               % (job_id, instance.job.id))
        return cls(request, instance)


    def _uri_args(self):
        return (self.instance.job_id, self.instance.id), {}


    def short_representation(self):
        rep = super(QueueEntry, self).short_representation()
        if self.instance.host:
            host = (Host(self._request, self.instance.host)
                    .short_representation())
        else:
            host = None
        job = Job(self._request, self.instance.job)
        host = Host.from_optional_instance(self._request, self.instance.host)
        label = Label.from_optional_instance(self._request,
                                             self.instance.meta_host)
        atomic_group_class = AtomicGroupClass.from_optional_instance(
                self._request, self.instance.atomic_group)
        rep.update(
                {'job': job.short_representation(),
                 'host': host.short_representation(),
                 'label': label.short_representation(),
                 'atomic_group_class':
                     atomic_group_class.short_representation(),
                 'status': self.instance.status,
                 'execution_path': self.instance.execution_subdir,
                 'started_on': self._format_datetime(self.instance.started_on),
                 'aborted': bool(self.instance.aborted)})
        return rep


    def update(self, input_dict):
        if 'aborted' in input_dict:
            if input_dict['aborted'] != True:
                raise BadRequest('"aborted" can only be set to true')
            query = models.HostQueueEntry.objects.filter(pk=self.instance.pk)
            models.AclGroup.check_abort_permissions(query)
            rpc_utils.check_abort_synchronous_jobs(query)
            self.instance.abort(thread_local.get_user())


class HealthTask(resource_lib.Entry):
    _permitted_methods = ('GET',)

    @classmethod
    def from_uri_args(cls, request, hostname, task_id):
        instance = models.SpecialTask.objects.get(id=task_id)
        if instance.host.hostname != hostname:
            raise http.Http404('Incorrect hostname %r (expected %r)'
                               % (hostname, instance.host.hostname))
        return cls(request, instance)


    def _uri_args(self):
        return (self.instance.host.hostname, self.instance.id), {}


    def short_representation(self):
        rep = super(HealthTask, self).short_representation()
        host = Host(self._request, self.instance.host)
        queue_entry = QueueEntry.from_optional_instance(
                self._request, self.instance.queue_entry)
        rep.update(
                {'host': host.short_representation(),
                 'task_type': self.instance.task,
                 'started_on':
                     self._format_datetime(self.instance.time_started),
                 'status': self.instance.status,
                 'queue_entry': queue_entry.short_representation()
                 })
        return rep


    @classmethod
    def create_instance(cls, input_dict, containing_collection):
        cls._check_for_required_fields(input_dict, ('task_type',))
        host = containing_collection.base_entry.instance
        models.AclGroup.check_for_acl_violation_hosts((host,))
        return models.SpecialTask.schedule_special_task(host,
                                                        input_dict['task_type'])


    def update(self, input_dict):
        # Required for POST, doesn't actually support PUT
        pass


class ResourceDirectory(resource_lib.Resource):
    _permitted_methods = ('GET',)

    def handle_request(self):
        result = self.link()
        result.update({
                'atomic_group_classes':
                AtomicGroupClassCollection(self._request).link(),
                'labels': LabelCollection(self._request).link(),
                'users': UserCollection(self._request).link(),
                'acl_groups': AclCollection(self._request).link(),
                'hosts': HostCollection(self._request).link(),
                'tests': TestCollection(self._request).link(),
                'execution_info': ExecutionInfo(self._request).link(),
                'queue_entries_request':
                QueueEntriesRequest(self._request).link(),
                'jobs': JobCollection(self._request).link(),
                })
        return self._basic_response(result)
