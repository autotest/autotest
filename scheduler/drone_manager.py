import os, re, shutil, signal, subprocess, errno, time, heapq, traceback
import common, logging
from autotest_lib.client.common_lib import error, global_config
from autotest_lib.scheduler import email_manager, drone_utility, drones
from autotest_lib.scheduler import scheduler_config


WORKING_DIRECTORY = object() # see execute_command()


class DroneManagerError(Exception):
    pass


class CustomEquals(object):
    def _id(self):
        raise NotImplementedError


    def __eq__(self, other):
        if not isinstance(other, type(self)):
            return NotImplemented
        return self._id() == other._id()


    def __ne__(self, other):
        return not self == other


    def __hash__(self):
        return hash(self._id())


class Process(CustomEquals):
    def __init__(self, hostname, pid, ppid=None):
        self.hostname = hostname
        self.pid = pid
        self.ppid = ppid

    def _id(self):
        return (self.hostname, self.pid)


    def __str__(self):
        return '%s/%s' % (self.hostname, self.pid)


    def __repr__(self):
        return super(Process, self).__repr__() + '<%s>' % self


class PidfileId(CustomEquals):
    def __init__(self, path):
        self.path = path


    def _id(self):
        return self.path


    def __str__(self):
        return str(self.path)


class PidfileContents(object):
    process = None
    exit_status = None
    num_tests_failed = None

    def is_invalid(self):
        return False


class InvalidPidfile(object):
    def __init__(self, error):
        self.error = error


    def is_invalid(self):
        return True


    def __str__(self):
        return self.error


class DroneManager(object):
    """
    This class acts as an interface from the scheduler to drones, whether it be
    only a single "drone" for localhost or multiple remote drones.

    All paths going into and out of this class are relative to the full results
    directory, except for those returns by absolute_path().
    """
    def __init__(self):
        self._results_dir = None
        self._processes = {}
        self._process_set = set()
        self._pidfiles = {}
        self._pidfiles_second_read = {}
        self._pidfile_age = {}
        self._temporary_path_counter = 0
        self._drones = {}
        self._results_drone = None
        self._attached_files = {}
        self._drone_queue = []


    def initialize(self, base_results_dir, drone_hostnames,
                   results_repository_hostname):
        self._results_dir = base_results_dir
        drones.set_temporary_directory(os.path.join(
            base_results_dir, drone_utility._TEMPORARY_DIRECTORY))

        for hostname in drone_hostnames:
            drone = self._add_drone(hostname)
            drone.call('initialize', base_results_dir)

        if not self._drones:
            # all drones failed to initialize
            raise DroneManagerError('No valid drones found')

        self.refresh_drone_configs()

        logging.info('Using results repository on %s',
                     results_repository_hostname)
        self._results_drone = drones.get_drone(results_repository_hostname)
        # don't initialize() the results drone - we don't want to clear out any
        # directories and we don't need ot kill any processes


    def reinitialize_drones(self):
        self._call_all_drones('initialize', self._results_dir)


    def shutdown(self):
        for drone in self.get_drones():
            drone.shutdown()


    def _get_max_pidfile_refreshes(self):
        """
        Normally refresh() is called on every monitor_db.Dispatcher.tick().

        @returns: The number of refresh() calls before we forget a pidfile.
        """
        pidfile_timeout = global_config.global_config.get_config_value(
                scheduler_config.CONFIG_SECTION, 'max_pidfile_refreshes',
                type=int, default=2000)
        return pidfile_timeout


    def _add_drone(self, hostname):
        logging.info('Adding drone %s' % hostname)
        drone = drones.get_drone(hostname)
        self._drones[drone.hostname] = drone
        return drone


    def _remove_drone(self, hostname):
        self._drones.pop(hostname, None)


    def refresh_drone_configs(self):
        """
        Reread global config options for all drones.
        """
        config = global_config.global_config
        section = scheduler_config.CONFIG_SECTION
        config.parse_config_file()
        for hostname, drone in self._drones.iteritems():
            disabled = config.get_config_value(
                section, '%s_disabled' % hostname, default='')
            drone.enabled = not bool(disabled)

            drone.max_processes = config.get_config_value(
                section, '%s_max_processes' % hostname, type=int,
                default=scheduler_config.config.max_processes_per_drone)


    def get_drones(self):
        return self._drones.itervalues()


    def _get_drone_for_process(self, process):
        return self._drones[process.hostname]


    def _get_drone_for_pidfile_id(self, pidfile_id):
        pidfile_contents = self.get_pidfile_contents(pidfile_id)
        assert pidfile_contents.process is not None
        return self._get_drone_for_process(pidfile_contents.process)


    def _drop_old_pidfiles(self):
        for pidfile_id, age in self._pidfile_age.items():
            if age > self._get_max_pidfile_refreshes():
                logging.info('forgetting pidfile %s', pidfile_id)
                del self._pidfile_age[pidfile_id]
            else:
                self._pidfile_age[pidfile_id] += 1


    def _reset(self):
        self._processes = {}
        self._process_set = set()
        self._pidfiles = {}
        self._pidfiles_second_read = {}
        self._drone_queue = []


    def _call_all_drones(self, method, *args, **kwargs):
        all_results = {}
        for drone in self.get_drones():
            all_results[drone] = drone.call(method, *args, **kwargs)
        return all_results


    def _parse_pidfile(self, drone, raw_contents):
        contents = PidfileContents()
        if not raw_contents:
            return contents
        lines = raw_contents.splitlines()
        if len(lines) > 3:
            return InvalidPidfile('Corrupt pid file (%d lines):\n%s' %
                                  (len(lines), lines))
        try:
            pid = int(lines[0])
            contents.process = Process(drone.hostname, pid)
            # if len(lines) == 2, assume we caught Autoserv between writing
            # exit_status and num_failed_tests, so just ignore it and wait for
            # the next cycle
            if len(lines) == 3:
                contents.exit_status = int(lines[1])
                contents.num_tests_failed = int(lines[2])
        except ValueError, exc:
            return InvalidPidfile('Corrupt pid file: ' + str(exc.args))

        return contents


    def _process_pidfiles(self, drone, pidfiles, store_in_dict):
        for pidfile_path, contents in pidfiles.iteritems():
            pidfile_id = PidfileId(pidfile_path)
            contents = self._parse_pidfile(drone, contents)
            store_in_dict[pidfile_id] = contents


    def _add_process(self, drone, process_info):
        process = Process(drone.hostname, int(process_info['pid']),
                          int(process_info['ppid']))
        self._process_set.add(process)
        return process


    def _add_autoserv_process(self, drone, process_info):
        assert process_info['comm'] == 'autoserv'
        # only root autoserv processes have pgid == pid
        if process_info['pgid'] != process_info['pid']:
            return
        process = self._add_process(drone, process_info)
        execution_tag = self._execution_tag_for_process(drone, process_info)
        self._processes[execution_tag] = process


    def _enqueue_drone(self, drone):
        heapq.heappush(self._drone_queue, (drone.used_capacity(), drone))


    def refresh(self):
        """
        Called at the beginning of a scheduler cycle to refresh all process
        information.
        """
        self._reset()
        self._drop_old_pidfiles()
        pidfile_paths = [pidfile_id.path for pidfile_id in self._pidfile_age]
        all_results = self._call_all_drones('refresh', pidfile_paths)

        for drone, results_list in all_results.iteritems():
            results = results_list[0]
            drone.active_processes = len(results['autoserv_processes'])
            if drone.enabled:
                self._enqueue_drone(drone)

            for process_info in results['autoserv_processes']:
                self._add_autoserv_process(drone, process_info)
            for process_info in results['parse_processes']:
                self._add_process(drone, process_info)

            self._process_pidfiles(drone, results['pidfiles'], self._pidfiles)
            self._process_pidfiles(drone, results['pidfiles_second_read'],
                                   self._pidfiles_second_read)


    def _execution_tag_for_process(self, drone, process_info):
        execution_tag = self._extract_execution_tag(process_info['args'])
        if not execution_tag:
            # this process has no execution tag - just make up something unique
            return '%s.%s' % (drone, process_info['pid'])
        return execution_tag


    def _extract_execution_tag(self, command):
        match = re.match(r'.* -P (\S+)', command)
        if not match:
            return None
        return match.group(1)


    def execute_actions(self):
        """
        Called at the end of a scheduler cycle to execute all queued actions
        on drones.
        """
        for drone in self._drones.values():
            drone.execute_queued_calls()

        try:
            self._results_drone.execute_queued_calls()
        except error.AutoservError:
            warning = ('Results repository failed to execute calls:\n' +
                       traceback.format_exc())
            email_manager.manager.enqueue_notify_email(
                'Results repository error', warning)
            self._results_drone.clear_call_queue()


    def get_orphaned_autoserv_processes(self):
        """
        Returns a set of Process objects for orphaned processes only.
        """
        return set(process for process in self._process_set
                   if process.ppid == 1)


    def get_process_for(self, execution_tag):
        """
        Return the process object for the given execution tag.
        """
        return self._processes.get(execution_tag, None)


    def kill_process(self, process):
        """
        Kill the given process.
        """
        logging.info('killing %s', process)
        drone = self._get_drone_for_process(process)
        drone.queue_call('kill_process', process)


    def _ensure_directory_exists(self, path):
        if not os.path.exists(path):
            os.makedirs(path)


    def _extract_num_processes(self, command):
        try:
            machine_list_index = command.index('-m') + 1
        except ValueError:
            return 1
        assert machine_list_index < len(command)
        machine_list = command[machine_list_index].split(',')
        return len(machine_list)


    def total_running_processes(self):
        return sum(drone.active_processes for drone in self.get_drones())


    def max_runnable_processes(self):
        """
        Return the maximum number of processes that can be run (in a single
        execution) given the current load on drones.
        """
        if not self._drone_queue:
            # all drones disabled
            return 0
        return max(drone.max_processes - drone.active_processes
                   for _, drone in self._drone_queue)


    def _least_loaded_drone(self, drones):
        drone_to_use = drones[0]
        for drone in drones[1:]:
            if drone.used_capacity() < drone_to_use.used_capacity():
                drone_to_use = drone
        return drone_to_use


    def _choose_drone_for_execution(self, num_processes):
        # cycle through drones is order of increasing used capacity until
        # we find one that can handle these processes
        checked_drones = []
        drone_to_use = None
        while self._drone_queue:
            used_capacity, drone = heapq.heappop(self._drone_queue)
            checked_drones.append(drone)
            if drone.active_processes + num_processes <= drone.max_processes:
                drone_to_use = drone
                break

        if not drone_to_use:
            drone_summary = ','.join('%s %s/%s' % (drone.hostname,
                                                   drone.active_processes,
                                                   drone.max_processes)
                                     for drone in checked_drones)
            logging.error('No drone has capacity to handle %d processes (%s)',
                          num_processes, drone_summary)
            drone_to_use = self._least_loaded_drone(checked_drones)

        drone_to_use.active_processes += num_processes

        # refill _drone_queue
        for drone in checked_drones:
            self._enqueue_drone(drone)

        return drone_to_use


    def _substitute_working_directory_into_command(self, command,
                                                   working_directory):
        for i, item in enumerate(command):
            if item is WORKING_DIRECTORY:
                command[i] = working_directory


    def execute_command(self, command, working_directory, pidfile_name,
                        log_file=None, paired_with_pidfile=None):
        """
        Execute the given command, taken as an argv list.

        @param command: command to execute as a list.  if any item is
                WORKING_DIRECTORY, the absolute path to the working directory
                will be substituted for it.
        @param working_directory: directory in which the pidfile will be written
        @param pidfile_name: name of the pidfile this process will write
        @param log_file (optional): path (in the results repository) to hold
                command output.
        @param paired_with_pidfile (optional): a PidfileId for an
                already-executed process; the new process will execute on the
                same drone as the previous process.
        """
        abs_working_directory = self.absolute_path(working_directory)
        if not log_file:
            log_file = self.get_temporary_path('execute')
        log_file = self.absolute_path(log_file)

        self._substitute_working_directory_into_command(command,
                                                        abs_working_directory)

        if paired_with_pidfile:
            drone = self._get_drone_for_pidfile_id(paired_with_pidfile)
        else:
            num_processes = self._extract_num_processes(command)
            drone = self._choose_drone_for_execution(num_processes)
        logging.info("command = %s" % command)
        logging.info('log file = %s:%s' % (drone.hostname, log_file))
        self._write_attached_files(working_directory, drone)
        drone.queue_call('execute_command', command, abs_working_directory,
                         log_file, pidfile_name)

        pidfile_path = self.absolute_path(os.path.join(abs_working_directory,
                                                       pidfile_name))
        pidfile_id = PidfileId(pidfile_path)
        self.register_pidfile(pidfile_id)
        return pidfile_id


    def get_pidfile_id_from(self, execution_tag, pidfile_name):
        path = os.path.join(self.absolute_path(execution_tag), pidfile_name)
        return PidfileId(path)


    def register_pidfile(self, pidfile_id):
        """
        Indicate that the DroneManager should look for the given pidfile when
        refreshing.
        """
        if pidfile_id not in self._pidfile_age:
            logging.info('monitoring pidfile %s', pidfile_id)
        self._pidfile_age[pidfile_id] = 0


    def get_pidfile_contents(self, pidfile_id, use_second_read=False):
        """
        Retrieve a PidfileContents object for the given pidfile_id.  If
        use_second_read is True, use results that were read after the processes
        were checked, instead of before.
        """
        self.register_pidfile(pidfile_id)
        if use_second_read:
            pidfile_map = self._pidfiles_second_read
        else:
            pidfile_map = self._pidfiles
        return pidfile_map.get(pidfile_id, PidfileContents())


    def is_process_running(self, process):
        """
        Check if the given process is in the running process list.
        """
        return process in self._process_set


    def get_temporary_path(self, base_name):
        """
        Get a new temporary path guaranteed to be unique across all drones
        for this scheduler execution.
        """
        self._temporary_path_counter += 1
        return os.path.join(drone_utility._TEMPORARY_DIRECTORY,
                            '%s.%s' % (base_name, self._temporary_path_counter))


    def absolute_path(self, path):
        return os.path.join(self._results_dir, path)


    def _copy_results_helper(self, process, source_path, destination_path,
                             to_results_repository=False):
        full_source = self.absolute_path(source_path)
        full_destination = self.absolute_path(destination_path)
        source_drone = self._get_drone_for_process(process)
        if to_results_repository:
            source_drone.send_file_to(self._results_drone, full_source,
                                      full_destination, can_fail=True)
        else:
            source_drone.queue_call('copy_file_or_directory', full_source,
                                    full_destination)


    def copy_to_results_repository(self, process, source_path,
                                   destination_path=None):
        """
        Copy results from the given process at source_path to destination_path
        in the results repository.
        """
        if destination_path is None:
            destination_path = source_path
        self._copy_results_helper(process, source_path, destination_path,
                                  to_results_repository=True)


    def copy_results_on_drone(self, process, source_path, destination_path):
        """
        Copy a results directory from one place to another on the drone.
        """
        self._copy_results_helper(process, source_path, destination_path)


    def _write_attached_files(self, results_dir, drone):
        attached_files = self._attached_files.pop(results_dir, {})
        for file_path, contents in attached_files.iteritems():
            drone.queue_call('write_to_file', self.absolute_path(file_path),
                             contents)


    def attach_file_to_execution(self, results_dir, file_contents,
                                 file_path=None):
        """
        When the process for the results directory is executed, the given file
        contents will be placed in a file on the drone.  Returns the path at
        which the file will be placed.
        """
        if not file_path:
            file_path = self.get_temporary_path('attach')
        files_for_execution = self._attached_files.setdefault(results_dir, {})
        assert file_path not in files_for_execution
        files_for_execution[file_path] = file_contents
        return file_path


    def write_lines_to_file(self, file_path, lines, paired_with_process=None):
        """
        Write the given lines (as a list of strings) to a file.  If
        paired_with_process is given, the file will be written on the drone
        running the given Process.  Otherwise, the file will be written to the
        results repository.
        """
        full_path = os.path.join(self._results_dir, file_path)
        file_contents = '\n'.join(lines) + '\n'
        if paired_with_process:
            drone = self._get_drone_for_process(paired_with_process)
        else:
            drone = self._results_drone
        drone.queue_call('write_to_file', full_path, file_contents)
