"""
Host Scheduler classes.
"""


class HostSchedulingUtility(object):

    """Interface to host availability information from the scheduler."""

    def hosts_in_label(self, label_id):
        """Return potentially usable hosts with the given label."""
        raise NotImplementedError

    def remove_host_from_label(self, host_id, label_id):
        """Remove this host from the internal list of usable hosts in the label.

        This is provided as an optimization -- when code gets a host from a
        label and concludes it's unusable, it can call this to avoid getting
        that host again in the future (within this tick).  This function should
        not affect correctness.
        """
        raise NotImplementedError

    def pop_host(self, host_id):
        """Remove and return a host from the internal list of available hosts.
        """
        raise NotImplementedError

    def ineligible_hosts_for_entry(self, queue_entry):
        """Get the list of hosts ineligible to run the given queue entry."""
        raise NotImplementedError

    def is_host_usable(self, host_id):
        """Determine if the host is currently usable at all."""
        raise NotImplementedError

    def is_host_eligible_for_job(self, host_id, queue_entry):
        """Determine if the host is eligible specifically for this queue entry.

        :param queue_entry: a HostQueueEntry DBObject
        """
        raise NotImplementedError


class MetahostScheduler(object):

    def can_schedule_metahost(self, queue_entry):
        """Return true if this object can schedule the given queue entry.

        At most one MetahostScheduler should return true for any given entry.

        :param queue_entry: a HostQueueEntry DBObject
        """
        raise NotImplementedError

    def schedule_metahost(self, queue_entry, scheduling_utility):
        """Schedule the given queue entry, if possible.

        This method should make necessary database changes culminating in
        assigning a host to the given queue entry in the database.  It may
        take no action if no host can be assigned currently.

        :param queue_entry: a HostQueueEntry DBObject
        :param scheduling_utility: a HostSchedulingUtility object
        """
        raise NotImplementedError

    def recovery_on_startup(self):
        """Perform any necessary recovery upon scheduler startup."""
        pass

    def tick(self):
        """Called once per scheduler cycle; any actions are allowed."""
        pass


class LabelMetahostScheduler(MetahostScheduler):

    def can_schedule_metahost(self, queue_entry):
        return bool(queue_entry.meta_host)

    def schedule_metahost(self, queue_entry, scheduling_utility):
        label_id = queue_entry.meta_host
        hosts_in_label = scheduling_utility.hosts_in_label(label_id)
        ineligible_host_ids = scheduling_utility.ineligible_hosts_for_entry(
            queue_entry)

        for host_id in hosts_in_label:
            if not scheduling_utility.is_host_usable(host_id):
                scheduling_utility.remove_host_from_label(host_id, label_id)
                continue
            if host_id in ineligible_host_ids:
                continue
            if not scheduling_utility.is_host_eligible_for_job(host_id,
                                                               queue_entry):
                continue

            # Remove the host from our cached internal state before returning
            scheduling_utility.remove_host_from_label(host_id, label_id)
            host = scheduling_utility.pop_host(host_id)
            queue_entry.set_host(host)
            return


def get_metahost_schedulers():
    return [LabelMetahostScheduler()]
