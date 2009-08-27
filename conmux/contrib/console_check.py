#!/usr/bin/python

_author_ = 'Scott Zawalski (scottz@google.com)'

"""Console check script to be used with conmux.

   Checks if machines are not only connected to conmux but also
   responding in an expected way

   Supports options to show all, good, bad, unknown and add them
   to autotest as well.

   *In order for the power update option to work you have to have
   access to the etc directory of the conmux server
"""

import sys,  pexpect, commands, os
from optparse import OptionParser


def main(argv):
    consoles = {}
    consoles['good'] = []
    consoles['bad'] = []
    consoles['unknown'] = []
    # 0, 1, 2 status
    STATUS = [ 'good', 'bad', 'unknown']
    parser = OptionParser()
    parser.add_option('--conmux-server', dest="conmux_server",
                     default='localhost',
                     help="Conmux server to connect to")
    parser.add_option('--conmux-dir', dest="conmux_dir",
                     default='/usr/local/conmux',
                     help="Conmux server to connect to")
    parser.add_option('--console-binary', dest="console_binary",
                     default='/usr/local/conmux/bin/console',
                     help="Conmux console binary location")
    parser.add_option('--autotest-cli-dir', dest="autotest_cli_dir",
                     default='/usr/local/autotest/cli',
                     help="Autotest CLI dir")
    parser.add_option('--add-hosts',
                      action="store_true", dest="add_hosts",
                      default=False,
                      help="If host not on autotest server try to add it")
    parser.add_option('--power-label', dest="power_label",
                     default='remote-power',
                     help="Label to add to hosts that support hard reset")
    parser.add_option('--console-label', dest="console_label",
                     default='console',
                     help="Label to add to hosts that support console")
    parser.add_option('--update-console-label',
                      action="store_true", dest="update_console_label",
                      default=False,
                      help="Update console label on autotest server")
    parser.add_option('--update-power-label',
                      action="store_true", dest="update_power_label",
                      default=False,
                      help="Update power label on autotest server" +\
                            "*Note this runs then exists no consoles are checked")
    parser.add_option('--verbose',
                      action="store_true", dest="verbose",
                      default=False,
                      help="Verbose output")
    parser.add_option('--show-bad',
                      action="store_true", dest="show_bad",
                      default=False,
                      help="Show consoles that are no longer functioning")
    parser.add_option('--show-good',
                      action="store_true", dest="show_good",
                      default=False,
                      help="Show consoles that are functioning properly")
    parser.add_option('--show-unknown',
                      action="store_true", dest="show_unknown",
                      default=False,
                      help="Show consoles that are in an unknown state")
    parser.add_option('--show-all',
                      action="store_true", dest="show_all",
                      default=False,
                      help="Show status of all consoles")
    options, args = parser.parse_args()
    if len(argv) == 2 and options.verbose:
        parser.print_help()
        return 1
    elif len(argv) < 2:
        parser.print_help()
        return 1

    if options.update_power_label:
        remove_create_label(options.power_label,
                            options.autotest_cli_dir)
        update_power_label(options.power_label, options.conmux_dir,
                           options.autotest_cli_dir, options.add_hosts)
        return
    print options.console_binary
    if not os.path.exists(options.console_binary):
        print "Error %s does not exist, please specify another path" %\
              options.console_binary
        return 1
    hosts = get_console_hosts(options.console_binary, options.conmux_server)
    for host in hosts:
        rc = check_host(host, options.console_binary)
        if options.verbose is True:
            print "%s status: %s" % (host, STATUS[rc])
        consoles[STATUS[rc]].append(host)

    if options.show_all:
        for status in consoles:
            print "--- %s ---" % status
            for host in consoles[status]:
                print host
    if options.show_good:
        print "--- good ---"
        for host in consoles['good']:
            print host
    if options.show_bad:
        print "--- bad ---"
        for host in consoles['bad']:
            print host
    if options.show_unknown:
        print "--- unknown ---"
        for host in consoles['unknown']:
            print host

    if options.update_console_label:
        remove_create_label(options.console_label,
                            options.autotest_cli_dir)
        update_console_label(options.console_label, consoles['good'],
                             options.autotest_cli_dir, options.add_hosts)


def update_console_label(console_label, consoles, cli_dir, add_hosts=False):
    """Update CONSOLE_LABEL on your autotest server.
       This removes the label and recreates it, then populating the label
       with all the machines your conmux server knows about.

       *Note If the hosts do not exist they are created.
       Args:
            console_label:
            string, describes the autotest label to add to machines.
            consoles:
            list, all the consoles that have confirmed console support.
    """
    # TODO: Update to new CLI and change logic until then
    # this is the best way to ensure a machine is added i.e. one at a time

    for host in consoles:
        if not host_label_add(host, console_label, cli_dir):
            # Try to create host
            if add_hosts:
                if host_create(host, cli_dir):
                    host_label_add(host, power_label,
                                   cli_dir)
                else:
                    print "Unable to add host " + host


def update_power_label(power_label, conmux_dir, cli_dir, add_hosts=False):
    """Look in CONSOLE_DIR/etc and grab known power commands
       Then remove POWER_LABEL and add machines to that label
    """
    # remove label and add it
    for host in hard_reset_hosts(conmux_dir):
        rc = label_add_host(host, power_label, cli_dir)
        if not rc:
            # Try to create the host
            if add_hosts:
                if host_create(host, cli_dir):
                    rc = label_add_host(host, power_label,
                                        cli_dir)
                else:
                    print "Unable to add host " + host


def hard_reset_hosts(conmux_dir):
    """Go through conmux dir and find hosts that have reset commands"""
    config_dir = os.path.join(conmux_dir, "etc")
    hosts = []
    for file in os.listdir(config_dir):
        if not file.endswith(".cf"):
            continue
        file_path = os.path.join(config_dir, file)
        try:
            try:
                f = open(file_path)
                for line in f:
                    if "reset" in line:
                        hosts.append(file.rstrip(".cf"))
            except IOError:
                pass
        finally:
            f.close()
    return hosts


def host_create(host, cli_dir):
    """Create a host
       Return:
            True, if successfuly false if failed
    """
    cmd = "%s/host-create %s" % (cli_dir, host)
    status, output = commands.getstatusoutput(cmd)
    return status == 0


def label_add_host(host, label, cli_dir):
    """Add a host to a label"""
    host_cmd = "%s/label-add-hosts %s %s" % (cli_dir, label, host)
    (status, output) = commands.getstatusoutput(host_cmd)
    if status != 0:
        return False

    return True


def remove_create_label(label, cli_dir):
    """Remove and recreate a given label"""
    cmd = "%s/label-rm %s" % (cli_dir, label)
    status, output = commands.getstatusoutput(cmd)
    if status != 0:
        raise Exception("Error deleting label: " + label)

    cmd = "%s/label-create %s" % (cli_dir, label)
    status, output = commands.getstatusoutput(cmd)
    if status != 0:
        raise Exception("Error creating label: " + label + output)

    return True


def get_console_hosts(console_binary, conmux_server):
    """Use console to collect console hosts and return a list.

       Args:
            console_binary:
            string, location of the conmux console binary
            conmux_server:
            string, hostname of the conmux server

       Returns:
            A List of console conmux is currently running on.
    """

    hosts_list = []
    cmd = "%s --list %s" % (console_binary, conmux_server)
    for line in commands.getoutput(cmd).split('\n'):
        host = (line.split(' '))[0]
        hosts_list.append(host)

    return hosts_list


def check_host(host, console_binary):
    """Check hosts for common errors and return the status.

       Args:
            host:
            string, the console host identifier

            console_binary:
            string, location of the conmux console binary
       Returns:
            int, 0: Machine state is good
            int, 1: Machine state is bad
            int, 2: Machine state is unknown
    """
    RESPONSES = [ host + ' login:',
                  'ENOENT entry not found',
                  'login:',
                  'Connection refused',
                  '<<<NOT CONNECTED>>>',
                  'Authentication failure',
                  'Give root password for maintenance', ]

    cmd = '%s %s' % (console_binary, host)
    shell = pexpect.spawn(cmd)

    shell.send('\r\n')
    shell.send('\r\n')
    shell.send('\r\n')
    try:
        # May need to increase the timeout but good so far
        response = shell.expect(RESPONSES, 1)
    except pexpect.TIMEOUT:
        shell.sendline('~$')
        shell.expect('>')
        shell.sendline('quit')
        return 1
    except pexpect.EOF:
        # unknown error
        shell.sendline('~$')
        shell.expect('>')
        shell.sendline('quit')
        return 2
    # TODO: Change actions based on what server returned
    if response == 0:
        # OK response
        return 0
    else:
        return 1


if __name__ == '__main__':
    main(sys.argv)
