import pickle, os, tempfile, logging
import common
from autotest_lib.scheduler import drone_utility, email_manager
from autotest_lib.client.common_lib import error, global_config


AUTOTEST_INSTALL_DIR = global_config.global_config.get_config_value('SCHEDULER',
                                                 'drone_installation_directory')

class _AbstractDrone(object):
    def __init__(self):
        self._calls = []
        self.hostname = None
        self.enabled = True
        self.max_processes = 0
        self.active_processes = 0


    def shutdown(self):
        pass


    def used_capacity(self):
        if self.max_processes == 0:
            return 1.0
        return float(self.active_processes) / self.max_processes


    def _execute_calls_impl(self, calls):
        raise NotImplementedError


    def _execute_calls(self, calls):
        return_message = self._execute_calls_impl(calls)
        for warning in return_message['warnings']:
            subject = 'Warning from drone %s' % self.hostname
            logging.warn(subject + '\n' + warning)
            email_manager.manager.enqueue_notify_email(subject, warning)
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
    _temporary_directory = None

    def __init__(self, hostname):
        super(_RemoteDrone, self).__init__()
        self.hostname = hostname
        self._host = drone_utility.create_host(hostname)
        self._drone_utility_path = os.path.join(AUTOTEST_INSTALL_DIR,
                                                'scheduler',
                                                'drone_utility.py')

        try:
            self._host.run('mkdir -p ' + self._temporary_directory,
                           timeout=10)
        except error.AutoservError:
            pass


    @classmethod
    def set_temporary_directory(cls, temporary_directory):
        cls._temporary_directory = temporary_directory


    def shutdown(self):
        super(_RemoteDrone, self).shutdown()
        self._host.close()


    def _execute_calls_impl(self, calls):
        calls_fd, calls_filename = tempfile.mkstemp(suffix='.pickled_calls')
        calls_file = os.fdopen(calls_fd, 'w+')
        pickle.dump(calls, calls_file)
        calls_file.flush()
        calls_file.seek(0)

        try:
            logging.info("Running drone_utility on %s", self.hostname)
            result = self._host.run('python %s' % self._drone_utility_path,
                                    stdin=calls_file, connect_timeout=300)
        finally:
            calls_file.close()
            os.remove(calls_filename)

        try:
            return pickle.loads(result.stdout)
        except Exception: # pickle.loads can throw all kinds of exceptions
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


def set_temporary_directory(temporary_directory):
    _RemoteDrone.set_temporary_directory(temporary_directory)


def get_drone(hostname):
    """
    Use this factory method to get drone objects.
    """
    if hostname == 'localhost':
        return _LocalDrone()
    return _RemoteDrone(hostname)
