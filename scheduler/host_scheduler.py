"""
Autotest scheduling utility.
"""
import logging

from autotest.client.shared import utils
from autotest.client.shared.settings import settings
from autotest.frontend.afe import models
from autotest.scheduler import metahost_scheduler, scheduler_config
from autotest.scheduler import scheduler_models


get_site_metahost_schedulers = utils.import_site_function(
    __file__, 'autotest.scheduler.site_metahost_scheduler',
    'get_metahost_schedulers', lambda: ())


class SchedulerError(Exception):

    """Raised by HostScheduler when an inconsistent state occurs."""


class BaseHostScheduler(metahost_scheduler.HostSchedulingUtility):

    """Handles the logic for choosing when to run jobs and on which hosts.

    This class makes several queries to the database on each tick, building up
    some auxiliary data structures and using them to determine which hosts are
    eligible to run which jobs, taking into account all the various factors that
    affect that.

    In the past this was done with one or two very large, complex database
    queries.  It has proven much simpler and faster to build these auxiliary
    data structures and perform the logic in Python.
    """

    def __init__(self, db):
        self._db = db
        self._metahost_schedulers = metahost_scheduler.get_metahost_schedulers()

        # load site-specific scheduler selected in settings
        site_schedulers_str = settings.get_value(
            scheduler_config.CONFIG_SECTION, 'site_metahost_schedulers',
            default='')
        site_schedulers = set(site_schedulers_str.split(','))
        for scheduler in get_site_metahost_schedulers():
            if type(scheduler).__name__ in site_schedulers:
                # always prepend, so site schedulers take precedence
                self._metahost_schedulers = (
                    [scheduler] + self._metahost_schedulers)
        logging.info('Metahost schedulers: %s',
                     ', '.join(type(scheduler).__name__ for scheduler
                               in self._metahost_schedulers))

    def _get_ready_hosts(self):
        # avoid any host with a currently active queue entry against it
        hosts = scheduler_models.Host.fetch(
            joins='LEFT JOIN afe_host_queue_entries AS active_hqe '
                  'ON (afe_hosts.id = active_hqe.host_id AND '
            'active_hqe.active)',
            where="active_hqe.host_id IS NULL "
                  "AND NOT afe_hosts.locked "
                  "AND (afe_hosts.status IS NULL "
            "OR afe_hosts.status = 'Ready')")
        return dict((host.id, host) for host in hosts)

    def _get_sql_id_list(self, id_list):
        return ','.join(str(item_id) for item_id in id_list)

    def _get_many2many_dict(self, query, id_list, flip=False):
        if not id_list:
            return {}
        query %= self._get_sql_id_list(id_list)
        rows = self._db.execute(query)
        return self._process_many2many_dict(rows, flip)

    def _process_many2many_dict(self, rows, flip=False):
        result = {}
        for row in rows:
            left_id, right_id = int(row[0]), int(row[1])
            if flip:
                left_id, right_id = right_id, left_id
            result.setdefault(left_id, set()).add(right_id)
        return result

    def _get_job_acl_groups(self, job_ids):
        query = """
        SELECT afe_jobs.id, afe_acl_groups_users.aclgroup_id
        FROM afe_jobs
        INNER JOIN afe_users ON afe_users.login = afe_jobs.owner
        INNER JOIN afe_acl_groups_users ON
                afe_acl_groups_users.user_id = afe_users.id
        WHERE afe_jobs.id IN (%s)
        """
        return self._get_many2many_dict(query, job_ids)

    def _get_job_ineligible_hosts(self, job_ids):
        query = """
        SELECT job_id, host_id
        FROM afe_ineligible_host_queues
        WHERE job_id IN (%s)
        """
        return self._get_many2many_dict(query, job_ids)

    def _get_job_dependencies(self, job_ids):
        query = """
        SELECT job_id, label_id
        FROM afe_jobs_dependency_labels
        WHERE job_id IN (%s)
        """
        return self._get_many2many_dict(query, job_ids)

    def _get_host_acls(self, host_ids):
        query = """
        SELECT host_id, aclgroup_id
        FROM afe_acl_groups_hosts
        WHERE host_id IN (%s)
        """
        return self._get_many2many_dict(query, host_ids)

    def _get_label_hosts(self, host_ids):
        if not host_ids:
            return {}, {}
        query = """
        SELECT label_id, host_id
        FROM afe_hosts_labels
        WHERE host_id IN (%s)
        """ % self._get_sql_id_list(host_ids)
        rows = self._db.execute(query)
        labels_to_hosts = self._process_many2many_dict(rows)
        hosts_to_labels = self._process_many2many_dict(rows, flip=True)
        return labels_to_hosts, hosts_to_labels

    def _get_labels(self):
        return dict((label.id, label) for label
                    in scheduler_models.Label.fetch())

    def recovery_on_startup(self):
        for metahost_scheduler in self._metahost_schedulers:
            metahost_scheduler.recovery_on_startup()

    def refresh(self, pending_queue_entries):
        self._hosts_available = self._get_ready_hosts()

        relevant_jobs = [queue_entry.job_id
                         for queue_entry in pending_queue_entries]
        self._job_acls = self._get_job_acl_groups(relevant_jobs)
        self._ineligible_hosts = self._get_job_ineligible_hosts(relevant_jobs)
        self._job_dependencies = self._get_job_dependencies(relevant_jobs)

        host_ids = self._hosts_available.keys()
        self._host_acls = self._get_host_acls(host_ids)
        self._label_hosts, self._host_labels = self._get_label_hosts(host_ids)

        self._labels = self._get_labels()

    def tick(self):
        for metahost_scheduler in self._metahost_schedulers:
            metahost_scheduler.tick()

    def hosts_in_label(self, label_id):
        return set(self._label_hosts.get(label_id, ()))

    def remove_host_from_label(self, host_id, label_id):
        self._label_hosts[label_id].remove(host_id)

    def pop_host(self, host_id):
        return self._hosts_available.pop(host_id)

    def ineligible_hosts_for_entry(self, queue_entry):
        return set(self._ineligible_hosts.get(queue_entry.job_id, ()))

    def _is_acl_accessible(self, host_id, queue_entry):
        job_acls = self._job_acls.get(queue_entry.job_id, set())
        host_acls = self._host_acls.get(host_id, set())
        return len(host_acls.intersection(job_acls)) > 0

    def _check_job_dependencies(self, job_dependencies, host_labels):
        missing = job_dependencies - host_labels
        return len(missing) == 0

    def _check_only_if_needed_labels(self, job_dependencies, host_labels,
                                     queue_entry):
        if not queue_entry.meta_host:
            # bypass only_if_needed labels when a specific host is selected
            return True

        for label_id in host_labels:
            label = self._labels[label_id]
            if not label.only_if_needed:
                # we don't care about non-only_if_needed labels
                continue
            if queue_entry.meta_host == label_id:
                # if the label was requested in a metahost it's OK
                continue
            if label_id not in job_dependencies:
                return False
        return True

    def _check_atomic_group_labels(self, host_labels, queue_entry):
        """
        Determine if the given HostQueueEntry's atomic group settings are okay
        to schedule on a host with the given labels.

        :param host_labels: A list of label ids that the host has.
        :param queue_entry: The HostQueueEntry being considered for the host.

        :return: True if atomic group settings are okay, False otherwise.
        """
        return (self._get_host_atomic_group_id(host_labels, queue_entry) ==
                queue_entry.atomic_group_id)

    def _get_host_atomic_group_id(self, host_labels, queue_entry=None):
        """
        Return the atomic group label id for a host with the given set of
        labels if any, or None otherwise.  Raises an exception if more than
        one atomic group are found in the set of labels.

        :param host_labels: A list of label ids that the host has.
        :param queue_entry: The HostQueueEntry we're testing.  Only used for
                extra info in a potential logged error message.

        :return: The id of the atomic group found on a label in host_labels
                or None if no atomic group label is found.
        """
        atomic_labels = [self._labels[label_id] for label_id in host_labels
                         if self._labels[label_id].atomic_group_id is not None]
        atomic_ids = set(label.atomic_group_id for label in atomic_labels)
        if not atomic_ids:
            return None
        if len(atomic_ids) > 1:
            logging.error('More than one Atomic Group on HQE "%s" via: %r',
                          queue_entry, atomic_labels)
        return atomic_ids.pop()

    def _get_atomic_group_labels(self, atomic_group_id):
        """
        Lookup the label ids that an atomic_group is associated with.

        :param atomic_group_id - The id of the AtomicGroup to look up.

        :return: A generator yielding Label ids for this atomic group.
        """
        return (id for id, label in self._labels.iteritems()
                if label.atomic_group_id == atomic_group_id
                and not label.invalid)

    def _get_eligible_host_ids_in_group(self, group_hosts, queue_entry):
        """
        :param group_hosts - A sequence of Host ids to test for usability
                and eligibility against the Job associated with queue_entry.
        :param queue_entry - The HostQueueEntry that these hosts are being
                tested for eligibility against.

        :return: A subset of group_hosts Host ids that are eligible for the
                supplied queue_entry.
        """
        return set(host_id for host_id in group_hosts
                   if self.is_host_usable(host_id)
                   and self.is_host_eligible_for_job(host_id, queue_entry))

    def is_host_eligible_for_job(self, host_id, queue_entry):
        if self._is_host_invalid(host_id):
            # if an invalid host is scheduled for a job, it's a one-time host
            # and it therefore bypasses eligibility checks. note this can only
            # happen for non-metahosts, because invalid hosts have their label
            # relationships cleared.
            return True

        job_dependencies = self._job_dependencies.get(queue_entry.job_id, set())
        host_labels = self._host_labels.get(host_id, set())

        return (self._is_acl_accessible(host_id, queue_entry) and
                self._check_job_dependencies(job_dependencies, host_labels) and
                self._check_only_if_needed_labels(
                    job_dependencies, host_labels, queue_entry) and
                self._check_atomic_group_labels(host_labels, queue_entry))

    def _is_host_invalid(self, host_id):
        host_object = self._hosts_available.get(host_id, None)
        return host_object and host_object.invalid

    def _schedule_non_metahost(self, queue_entry):
        if not self.is_host_eligible_for_job(queue_entry.host_id, queue_entry):
            return None
        return self._hosts_available.pop(queue_entry.host_id, None)

    def is_host_usable(self, host_id):
        if host_id not in self._hosts_available:
            # host was already used during this scheduling cycle
            return False
        if self._hosts_available[host_id].invalid:
            # Invalid hosts cannot be used for metahosts.  They're included in
            # the original query because they can be used by non-metahosts.
            return False
        return True

    def schedule_entry(self, queue_entry):
        if queue_entry.host_id is not None:
            return self._schedule_non_metahost(queue_entry)

        for scheduler in self._metahost_schedulers:
            if scheduler.can_schedule_metahost(queue_entry):
                scheduler.schedule_metahost(queue_entry, self)
                return None

        raise SchedulerError('No metahost scheduler to handle %s' % queue_entry)

    def find_eligible_atomic_group(self, queue_entry):
        """
        Given an atomic group host queue entry, locate an appropriate group
        of hosts for the associated job to run on.

        The caller is responsible for creating new HQEs for the additional
        hosts returned in order to run the actual job on them.

        :return: A list of Host instances in a ready state to satisfy this
                atomic group scheduling.  Hosts will all belong to the same
                atomic group label as specified by the queue_entry.
                An empty list will be returned if no suitable atomic
                group could be found.

        TODO(gps): what is responsible for kicking off any attempted repairs on
        a group of hosts?  not this function, but something needs to.  We do
        not communicate that reason for returning [] outside of here...
        For now, we'll just be unschedulable if enough hosts within one group
        enter Repair Failed state.
        """
        assert queue_entry.atomic_group_id is not None
        job = queue_entry.job
        assert job.synch_count and job.synch_count > 0
        atomic_group = queue_entry.atomic_group
        if job.synch_count > atomic_group.max_number_of_machines:
            # Such a Job and HostQueueEntry should never be possible to
            # create using the frontend.  Regardless, we can't process it.
            # Abort it immediately and log an error on the scheduler.
            queue_entry.set_status(models.HostQueueEntry.Status.ABORTED)
            logging.error(
                'Error: job %d synch_count=%d > requested atomic_group %d '
                'max_number_of_machines=%d.  Aborted host_queue_entry %d.',
                job.id, job.synch_count, atomic_group.id,
                atomic_group.max_number_of_machines, queue_entry.id)
            return []
        hosts_in_label = self.hosts_in_label(queue_entry.meta_host)
        ineligible_host_ids = self.ineligible_hosts_for_entry(queue_entry)

        # Look in each label associated with atomic_group until we find one with
        # enough hosts to satisfy the job.
        for atomic_label_id in self._get_atomic_group_labels(atomic_group.id):
            group_hosts = set(self.hosts_in_label(atomic_label_id))
            if queue_entry.meta_host is not None:
                # If we have a metahost label, only allow its hosts.
                group_hosts.intersection_update(hosts_in_label)
            group_hosts -= ineligible_host_ids
            eligible_host_ids_in_group = self._get_eligible_host_ids_in_group(
                group_hosts, queue_entry)

            # Job.synch_count is treated as "minimum synch count" when
            # scheduling for an atomic group of hosts.  The atomic group
            # number of machines is the maximum to pick out of a single
            # atomic group label for scheduling at one time.
            min_hosts = job.synch_count
            max_hosts = atomic_group.max_number_of_machines

            if len(eligible_host_ids_in_group) < min_hosts:
                # Not enough eligible hosts in this atomic group label.
                continue

            eligible_hosts_in_group = [self._hosts_available[id]
                                       for id in eligible_host_ids_in_group]
            # So that they show up in a sane order when viewing the job.
            eligible_hosts_in_group.sort(cmp=scheduler_models.Host.cmp_for_sort)

            # Limit ourselves to scheduling the atomic group size.
            if len(eligible_hosts_in_group) > max_hosts:
                eligible_hosts_in_group = eligible_hosts_in_group[:max_hosts]

            # Remove the selected hosts from our cached internal state
            # of available hosts in order to return the Host objects.
            host_list = []
            for host in eligible_hosts_in_group:
                hosts_in_label.discard(host.id)
                self._hosts_available.pop(host.id)
                host_list.append(host)
            return host_list

        return []


site_host_scheduler = utils.import_site_class(
    __file__, 'autotest.scheduler.site_host_scheduler',
    'site_host_scheduler', BaseHostScheduler)


class HostScheduler(site_host_scheduler):
    pass
