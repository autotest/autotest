import cPickle
import logging
import os

try:
    import autotest.common as common  # pylint: disable=W0611
except ImportError:
    import common  # pylint: disable=W0611
from autotest.scheduler import drone_utility
from autotest.client.shared.settings import settings
from autotest.client.shared import mail


AUTOTEST_INSTALL_DIR = settings.get_value('SCHEDULER',
                                          'drone_installation_directory')


class DroneUnreachable(Exception):

    """The drone is non-sshable."""
    pass


class _AbstractDrone(object):

    """
    Attributes:
    * allowed_users: set of usernames allowed to use this drone.  if None,
            any user can use this drone.
    """

    def __init__(self):
        self._calls = []
        self.hostname = None
        self.enabled = True
        self.max_processes = 0
        self.active_processes = 0
        self.allowed_users = None

    def shutdown(self):
        pass

    def used_capacity(self):
        """Gets the capacity used by this drone

        Returns a tuple of (percentage_full, -max_capacity). This is to aid
        direct comparisons, so that a 0/10 drone is considered less heavily
        loaded than a 0/2 drone.

        This value should never be used directly. It should only be used in
        direct comparisons using the basic comparison operators, or using the
        cmp() function.
        """
        if self.max_processes == 0:
            return (1.0, 0)
        return (float(self.active_processes) / self.max_processes,
                -self.max_processes)

    def usable_by(self, user):
        if self.allowed_users is None:
            return True
        return user in self.allowed_users

    def _execute_calls_impl(self, calls):
        raise NotImplementedError

    def _execute_calls(self, calls):
        return_message = self._execute_calls_impl(calls)
        for warning in return_message['warnings']:
            subject = 'Warning from drone %s' % self.hostname
            logging.warn(subject + '\n' + warning)
            mail.manager.enqueue_admin(subject, warning)
        return return_message['results']

    def call(self, method, *args, **kwargs):
        return self._execute_calls(
            [drone_utility.call(method, *args, **kwargs)])

    def queue_call(self, method, *args, **kwargs):
        self._calls.append(drone_utility.call(method, *args, **kwargs))

    def clear_call_queue(self):
        self._calls = []

    def execute_queued_calls(self):
        if not self._calls:
            return
        self._execute_calls(self._calls)
        self.clear_call_queue()

    def set_autotest_install_dir(self, path):
        pass


class _LocalDrone(_AbstractDrone):

    def __init__(self):
        super(_LocalDrone, self).__init__()
        self.hostname = 'localhost'
        self._drone_utility = drone_utility.DroneUtility()

    def _execute_calls_impl(self, calls):
        return self._drone_utility.execute_calls(calls)

    def send_file_to(self, drone, source_path, destination_path,
                     can_fail=False):
        if drone.hostname == self.hostname:
            self.queue_call('copy_file_or_directory', source_path,
                            destination_path)
        else:
            self.queue_call('send_file_to', drone.hostname, source_path,
                            destination_path, can_fail)


class _RemoteDrone(_AbstractDrone):

    def __init__(self, hostname):
        super(_RemoteDrone, self).__init__()
        self.hostname = hostname
        self._host = drone_utility.create_host(hostname)
        if not self._host.is_up():
            logging.error('Drone %s is unpingable, kicking out', hostname)
            raise DroneUnreachable
        self._autotest_install_dir = AUTOTEST_INSTALL_DIR

    @property
    def _drone_utility_path(self):
        return os.path.join(self._autotest_install_dir,
                            'scheduler', 'drone_utility.py')

    def set_autotest_install_dir(self, path):
        self._autotest_install_dir = path

    def shutdown(self):
        super(_RemoteDrone, self).shutdown()
        self._host.close()

    def _execute_calls_impl(self, calls):
        logging.info("Running drone_utility on %s", self.hostname)
        result = self._host.run('python %s' % self._drone_utility_path,
                                stdin=cPickle.dumps(calls), stdout_tee=None,
                                connect_timeout=300)
        try:
            return cPickle.loads(result.stdout)
        except Exception:  # cPickle.loads can throw all kinds of exceptions
            logging.critical('Invalid response:\n---\n%s\n---', result.stdout)
            raise

    def send_file_to(self, drone, source_path, destination_path,
                     can_fail=False):
        if drone.hostname == self.hostname:
            self.queue_call('copy_file_or_directory', source_path,
                            destination_path)
        elif isinstance(drone, _LocalDrone):
            drone.queue_call('get_file_from', self.hostname, source_path,
                             destination_path)
        else:
            self.queue_call('send_file_to', drone.hostname, source_path,
                            destination_path, can_fail)


def get_drone(hostname):
    """
    Use this factory method to get drone objects.
    """
    if hostname == 'localhost':
        return _LocalDrone()
    try:
        return _RemoteDrone(hostname)
    except DroneUnreachable:
        return None
