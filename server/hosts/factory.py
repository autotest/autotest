from autotest_lib.client.common_lib import utils, error
from autotest_lib.server import utils as server_utils
from autotest_lib.server.hosts import site_factory, abstract_ssh
from autotest_lib.server.hosts import ssh_host, serial, netconsole, dmesg


def create_host(hostname, auto_monitor=True, **args):
    # by default assume we're using SSH support
    classes = [ssh_host.SSHHost]

    if auto_monitor:
        # use serial console support if it's available
        conmux_args = {}
        for key in ("conmux_server", "conmux_attach"):
            if key in args:
                conmux_args[key] = args[key]
        if serial.SerialHost.host_is_supported(hostname, **conmux_args):
            classes.append(serial.SerialHost)
        else:
            # no serial host available, try netconsole logging if available
            def run_func(cmd):
                base_cmd = abstract_ssh.make_ssh_command(connect_timeout=3)
                full_cmd = '%s %s "%s"' % (base_cmd, hostname,
                                           server_utils.sh_escape(cmd))
                try:
                    utils.run(full_cmd)
                except error.CmdError:
                    pass

            if netconsole.NetconsoleHost.host_is_supported(run_func):
                classes.append(netconsole.NetconsoleHost)
            else:
                # nothing available, fall back to direct dmesg logging
                classes.append(dmesg.DmesgHost)

    # do any site-specific processing of the classes list
    site_factory.postprocess_classes(classes, hostname, 
                                     auto_monitor=auto_monitor, **args)

    # create a custom host class for this machine and return an instance of it
    host_class = type("%s_host" % hostname, tuple(classes), {})
    return host_class(hostname, **args)
