from autotest_lib.client.common_lib import utils, error, global_config
from autotest_lib.server import autotest, utils as server_utils
from autotest_lib.server.hosts import site_factory, ssh_host, serial
from autotest_lib.server.hosts import logfile_monitor

DEFAULT_FOLLOW_PATH = '/var/log/kern.log'
DEFAULT_PATTERNS_PATH = 'console_patterns'
SSH_ENGINE = global_config.global_config.get_config_value('AUTOSERV',
                                                          'ssh_engine',
                                                          type=str)

# for tracking which hostnames have already had job_start called
_started_hostnames = set()

def create_host(
    hostname, auto_monitor=True, follow_paths=None, pattern_paths=None,
    netconsole=False, **args):
    # by default assume we're using SSH support
    if SSH_ENGINE == 'paramiko':
        from autotest_lib.server.hosts import paramiko_host
        classes = [paramiko_host.ParamikoHost]
    elif SSH_ENGINE == 'raw_ssh':
        classes = [ssh_host.SSHHost, ssh_host.AsyncSSHMixin]
    else:
        raise error.AutoServError("Unknown SSH engine %s. Please verify the "
                                  "value of the configuration key 'ssh_engine' "
                                  "on autotest's global_config.ini file." %
                                  SSH_ENGINE)

    # by default mix in run_test support
    classes.append(autotest.AutotestHostMixin)

    # if the user really wants to use netconsole, let them
    if netconsole:
        classes.append(netconsole.NetconsoleHost)

    if auto_monitor:
        # use serial console support if it's available
        conmux_args = {}
        for key in ("conmux_server", "conmux_attach"):
            if key in args:
                conmux_args[key] = args[key]
        if serial.SerialHost.host_is_supported(hostname, **conmux_args):
            classes.append(serial.SerialHost)
        else:
            # no serial available, fall back to direct dmesg logging
            if follow_paths is None:
                follow_paths = [DEFAULT_FOLLOW_PATH]
            else:
                follow_paths = list(follow_paths) + [DEFAULT_FOLLOW_PATH]

            if pattern_paths is None:
                pattern_paths = [DEFAULT_PATTERNS_PATH]
            else:
                pattern_paths = (
                    list(pattern_paths) + [DEFAULT_PATTERNS_PATH])

            logfile_monitor_class = logfile_monitor.NewLogfileMonitorMixin(
                follow_paths, pattern_paths)
            classes.append(logfile_monitor_class)

    elif follow_paths:
        logfile_monitor_class = logfile_monitor.NewLogfileMonitorMixin(
            follow_paths, pattern_paths)
        classes.append(logfile_monitor_class)

    # do any site-specific processing of the classes list
    site_factory.postprocess_classes(classes, hostname,
                                     auto_monitor=auto_monitor, **args)

    hostname, args['user'], args['password'], args['port'] = \
            server_utils.parse_machine(hostname, ssh_user, ssh_pass, ssh_port)

    # create a custom host class for this machine and return an instance of it
    host_class = type("%s_host" % hostname, tuple(classes), {})
    host_instance = host_class(hostname, **args)

    # call job_start if this is the first time this host is being used
    if hostname not in _started_hostnames:
        host_instance.job_start()
        _started_hostnames.add(hostname)

    return host_instance
