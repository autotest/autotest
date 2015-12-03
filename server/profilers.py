import logging
import os
import shutil
import tempfile

try:
    import autotest.common as common  # pylint: disable=W0611
except ImportError:
    import common  # pylint: disable=W0611
from autotest.client.shared import utils, error, profiler_manager
from autotest.server import profiler, autotest_remote, standalone_profiler
from autotest.server import hosts


PROFILER_TMPDIR = '/tmp/profilers'


def get_profiler_results_dir(autodir):
    """
    Given the directory of the autotest_remote client used to run a profiler,
    return the remote path where profiler results will be stored.
    """
    return os.path.join(autodir, 'results', 'default', 'profiler_sync',
                        'profiling')


def get_profiler_log_path(autodir):
    """
    Given the directory of a profiler client, find the client log path.
    """
    return os.path.join(autodir, 'results', 'default', 'debug', 'client.DEBUG')


class profilers(profiler_manager.profiler_manager):

    def __init__(self, job):
        super(profilers, self).__init__(job)
        self.add_log = {}
        self.start_delay = 0
        # maps hostname to (host object, autotest_remote.Autotest object, Autotest
        # install dir), where the host object is the one created specifically
        # for profiling
        self.installed_hosts = {}
        self.current_test = None

    def set_start_delay(self, start_delay):
        self.start_delay = start_delay

    def load_profiler(self, profiler_name, args, dargs):
        newprofiler = profiler.profiler_proxy(profiler_name)
        newprofiler.initialize(*args, **dargs)
        newprofiler.setup(*args, **dargs)  # lazy setup is done client-side
        return newprofiler

    def add(self, profiler, *args, **dargs):
        super(profilers, self).add(profiler, *args, **dargs)
        self.add_log[profiler] = (args, dargs)

    def delete(self, profiler):
        super(profilers, self).delete(profiler)
        if profiler in self.add_log:
            del self.add_log[profiler]

    def _install_clients(self):
        """
        Install autotest_remote on any current job hosts.
        """
        in_use_hosts = set()
        # find hosts in use but not used by us
        for host in self.job.hosts:
            autodir = host.get_autodir()
            if not (autodir and autodir.startswith(PROFILER_TMPDIR)):
                in_use_hosts.add(host.hostname)
        logging.debug('Hosts currently in use: %s', in_use_hosts)

        # determine what valid host objects we already have installed
        profiler_hosts = set()
        for host, at, profiler_dir in self.installed_hosts.values():
            if host.path_exists(profiler_dir):
                profiler_hosts.add(host.hostname)
            else:
                # the profiler was wiped out somehow, drop this install
                logging.warning('The profiler client on %s at %s was deleted',
                                host.hostname, profiler_dir)
                host.close()
                del self.installed_hosts[host.hostname]
        logging.debug('Hosts with profiler clients already installed: %s',
                      profiler_hosts)

        # install autotest_remote on any new hosts in use
        for hostname in in_use_hosts - profiler_hosts:
            host = hosts.create_host(hostname, auto_monitor=False)
            tmp_dir = host.get_tmp_dir(parent=PROFILER_TMPDIR)
            at = autotest_remote.Autotest(host)
            at.install_no_autoserv(autodir=tmp_dir)
            self.installed_hosts[host.hostname] = (host, at, tmp_dir)

        # drop any installs from hosts no longer in job.hosts
        hostnames_to_drop = profiler_hosts - in_use_hosts
        hosts_to_drop = [self.installed_hosts[hostname][0]
                         for hostname in hostnames_to_drop]
        for host in hosts_to_drop:
            host.close()
            del self.installed_hosts[host.hostname]

    def _get_hosts(self, host=None):
        """
        Returns a list of (Host, Autotest, install directory) tuples for hosts
        currently supported by this profiler. The returned Host object is always
        the one created by this profiler, regardless of what's passed in. If
        'host' is not None, all entries not matching that host object are
        filtered out of the list.
        """
        if host is None:
            return self.installed_hosts.values()
        if host.hostname in self.installed_hosts:
            return [self.installed_hosts[host.hostname]]
        return []

    def _get_local_profilers_dir(self, test, hostname):
        in_machine_dir = (
            os.path.basename(test.job.resultdir) in test.job.machines)
        if len(test.job.machines) > 1 and not in_machine_dir:
            local_dir = os.path.join(test.profdir, hostname)
            if not os.path.exists(local_dir):
                os.makedirs(local_dir)
        else:
            local_dir = test.profdir

        return local_dir

    def _get_failure_logs(self, autodir, test, host):
        """
        Collect the client logs from a profiler run and put them in a
        file named failure-*.log.
        """
        try:
            fd, path = tempfile.mkstemp(suffix='.log', prefix='failure-',
                                        dir=self._get_local_profilers_dir(test, host.hostname))
            os.close(fd)
            host.get_file(get_profiler_log_path(autodir), path)
            # try to collect any partial profiler logs
            self._get_profiler_logs(autodir, test, host)
        except (error.AutotestError, error.AutoservError):
            logging.exception('Profiler failure log collection failed')
            # swallow the exception so that we don't override an existing
            # exception being thrown

    def _get_all_failure_logs(self, test, hosts):
        for host, at, autodir in hosts:
            self._get_failure_logs(autodir, test, host)

    def _get_profiler_logs(self, autodir, test, host):
        results_dir = get_profiler_results_dir(autodir)
        local_dir = self._get_local_profilers_dir(test, host.hostname)

        self.job.remove_client_log(host.hostname, results_dir, local_dir)

        tempdir = tempfile.mkdtemp(dir=self.job.tmpdir)
        try:
            host.get_file(results_dir + '/', tempdir)
        except error.AutoservRunError:
            pass  # no files to pull back, nothing we can do
        utils.merge_trees(tempdir, local_dir)
        shutil.rmtree(tempdir, ignore_errors=True)

    def _run_clients(self, test, hosts):
        """
        We initialize the profilers just before start because only then we
        know all the hosts involved.
        """

        hostnames = [host_info[0].hostname for host_info in hosts]
        profilers_args = [(p.name, p.args, p.dargs)
                          for p in self.list]

        for host, at, autodir in hosts:
            control_script = standalone_profiler.generate_test(hostnames,
                                                               host.hostname,
                                                               profilers_args,
                                                               180, None)
            try:
                at.run(control_script, background=True)
            except Exception:
                self._get_failure_logs(autodir, test, host)
                raise

            remote_results_dir = get_profiler_results_dir(autodir)
            local_results_dir = self._get_local_profilers_dir(test,
                                                              host.hostname)
            self.job.add_client_log(host.hostname, remote_results_dir,
                                    local_results_dir)

        try:
            # wait for the profilers to be added
            standalone_profiler.wait_for_profilers(hostnames)
        except Exception:
            self._get_all_failure_logs(test, hosts)
            raise

    def before_start(self, test, host=None):
        # create host objects and install the needed clients
        # so later in start() we don't spend too much time
        self._install_clients()
        self._run_clients(test, self._get_hosts(host))

    def start(self, test, host=None):
        hosts = self._get_hosts(host)

        # wait for the profilers to start
        hostnames = [host_info[0].hostname for host_info in hosts]
        try:
            standalone_profiler.start_profilers(hostnames)
        except Exception:
            self._get_all_failure_logs(test, hosts)
            raise

        self.current_test = test

    def stop(self, test):
        assert self.current_test == test

        hosts = self._get_hosts()
        # wait for the profilers to stop
        hostnames = [host_info[0].hostname for host_info in hosts]
        try:
            standalone_profiler.stop_profilers(hostnames)
        except Exception:
            self._get_all_failure_logs(test, hosts)
            raise

    def report(self, test, host=None):
        assert self.current_test == test

        hosts = self._get_hosts(host)
        # when running on specific hosts we cannot wait for the other
        # hosts to sync with us
        if not host:
            hostnames = [host_info[0].hostname for host_info in hosts]
            try:
                standalone_profiler.finish_profilers(hostnames)
            except Exception:
                self._get_all_failure_logs(test, hosts)
                raise

        # pull back all the results
        for host, at, autodir in hosts:
            self._get_profiler_logs(autodir, test, host)

    def handle_reboot(self, host):
        if self.current_test:
            test = self.current_test
            for profiler in self.list:
                if not profiler.supports_reboot:
                    msg = 'profiler %s does not support rebooting during tests'
                    msg %= profiler.name
                    self.job.record('WARN', os.path.basename(test.outputdir),
                                    None, msg)

            self.report(test, host)
            self.before_start(test, host)
            self.start(test, host)
