import atexit, datetime, os, tempfile, unittest
import common
from autotest_lib.frontend import setup_test_environment
from autotest_lib.frontend import thread_local
from autotest_lib.frontend.afe import models
from autotest_lib.client.common_lib.test_utils import mock

class FrontendTestMixin(object):
    _test_db_initialized = False

    def _initialize_test_db(self):
        if self._test_db_initialized:
            return

        temp_fd, test_db_file = tempfile.mkstemp(suffix='.frontend_test')
        FrontendTestMixin._test_db_file = test_db_file
        os.close(temp_fd)

        def cleanup_test_db():
            os.remove(test_db_file)
        atexit.register(cleanup_test_db)

        setup_test_environment.set_test_database(test_db_file)
        setup_test_environment.set_up()
        FrontendTestMixin._test_db_backup = (
            setup_test_environment.backup_test_database())
        FrontendTestMixin._test_db_initialized = True


    def _open_test_db(self):
        self._initialize_test_db()
        setup_test_environment.restore_test_database(self._test_db_backup)


    def _fill_in_test_data(self):
        """Populate the test database with some hosts and labels."""
        acl_group = models.AclGroup.objects.create(name='my_acl')
        acl_group.users.add(self.user)

        self.hosts = [models.Host.objects.create(hostname=hostname)
                      for hostname in
                      ('host1', 'host2', 'host3', 'host4', 'host5', 'host6',
                       'host7', 'host8', 'host9')]

        acl_group.hosts = self.hosts
        models.AclGroup.smart_get('Everyone').hosts = []

        labels = [models.Label.objects.create(name=name) for name in
                  ('label1', 'label2', 'label3', 'label4', 'label5', 'label6',
                   'label7', 'label8')]

        platform = models.Label.objects.create(name='myplatform', platform=True)
        for host in self.hosts:
            host.labels.add(platform)

        atomic_group1 = models.AtomicGroup.objects.create(
                name='atomic1', max_number_of_machines=2)
        atomic_group2 = models.AtomicGroup.objects.create(
                name='atomic2', max_number_of_machines=2)

        self.label3 = labels[2]
        self.label3.only_if_needed = True
        self.label3.save()
        self.label4 = labels[3]
        self.label4.atomic_group = atomic_group1
        self.label4.save()
        self.label5 = labels[4]
        self.label5.atomic_group = atomic_group1
        self.label5.save()
        self.hosts[0].labels.add(labels[0])  # label1
        self.hosts[1].labels.add(labels[1])  # label2
        self.label6 = labels[5]
        self.label7 = labels[6]
        self.label8 = labels[7]
        self.label8.atomic_group = atomic_group2
        self.label8.save()
        for hostnum in xrange(4,7):  # host5..host7
            self.hosts[hostnum].labels.add(self.label4)  # an atomic group lavel
            self.hosts[hostnum].labels.add(self.label6)  # a normal label
        self.hosts[6].labels.add(self.label7)
        for hostnum in xrange(7,9):  # host8..host9
            self.hosts[hostnum].labels.add(self.label5)  # an atomic group lavel
            self.hosts[hostnum].labels.add(self.label6)  # a normal label
            self.hosts[hostnum].labels.add(self.label7)


    def _setup_dummy_user(self):
        self.user = models.User.objects.create(login='my_user', access_level=0)
        thread_local.set_user(self.user)


    def _frontend_common_setup(self):
        self.god = mock.mock_god()
        self._open_test_db()
        self._setup_dummy_user()
        self._fill_in_test_data()


    def _frontend_common_teardown(self):
        setup_test_environment.tear_down()
        thread_local.set_user(None)
        self.god.unstub_all()


    def _create_job(self, hosts=[], metahosts=[], priority=0, active=False,
                    synchronous=False, atomic_group=None):
        """
        Create a job row in the test database.

        @param hosts - A list of explicit host ids for this job to be
                scheduled on.
        @param metahosts - A list of label ids for each host that this job
                should be scheduled on (meta host scheduling).
        @param priority - The job priority (integer).
        @param active - bool, mark this job as running or not in the database?
        @param synchronous - bool, if True use synch_count=2 otherwise use
                synch_count=1.
        @param atomic_group - An atomic group id for this job to schedule on
                or None if atomic scheduling is not required.  Each metahost
                becomes a request to schedule an entire atomic group.
                This does not support creating an active atomic group job.

        @returns A Django frontend.afe.models.Job instance.
        """
        assert not (atomic_group and active)  # TODO(gps): support this
        synch_count = synchronous and 2 or 1
        created_on = datetime.datetime(2008, 1, 1)
        status = models.HostQueueEntry.Status.QUEUED
        if active:
            status = models.HostQueueEntry.Status.RUNNING
        job = models.Job.objects.create(
            name='test', owner='my_user', priority=priority,
            synch_count=synch_count, created_on=created_on,
            reboot_before=models.RebootBefore.NEVER)
        for host_id in hosts:
            models.HostQueueEntry.objects.create(job=job, host_id=host_id,
                                                 status=status,
                                                 atomic_group_id=atomic_group)
            models.IneligibleHostQueue.objects.create(job=job, host_id=host_id)
        for label_id in metahosts:
            models.HostQueueEntry.objects.create(job=job, meta_host_id=label_id,
                                                 status=status,
                                                 atomic_group_id=atomic_group)
        if atomic_group and not (metahosts or hosts):
            # Create a single HQE to request the atomic group of hosts even if
            # no metahosts or hosts are supplied.
            models.HostQueueEntry.objects.create(job=job,
                                                 status=status,
                                                 atomic_group_id=atomic_group)
        return job


    def _create_job_simple(self, hosts, use_metahost=False,
                          priority=0, active=False):
        """An alternative interface to _create_job"""
        args = {'hosts' : [], 'metahosts' : []}
        if use_metahost:
            args['metahosts'] = hosts
        else:
            args['hosts'] = hosts
        return self._create_job(priority=priority, active=active, **args)
