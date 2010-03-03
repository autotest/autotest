#!/usr/bin/python
"""Service launcher that creates pidfiles and can redirect output to a file."""
import subprocess, sys, os, optparse, signal, pwd, grp, re


def stop_service(pidfile):
    """
    Stop a service using a pidfile.

    Read the first line of a file for an integer that should refer to a pid,
    send a SIGTERM to that pid #.
       @param pidfile: file to read for the process id number
    """
    pidfh = open(pidfile)
    pid = int(pidfh.readline())
    os.kill(pid, signal.SIGTERM)


def start_service(cmd, pidfile, logfile=os.devnull, chdir=None):
    """
    Start cmd in the background and write the pid to pidfile.

    @param cmd: command to run with arguments
    @param pidfile: pidfile to write the pid to
    @param logfile: file to write stderr/stdout to
    @param chdir: Directory to change to before starting the application
    """
    logfh = open(logfile, 'a')
    pidfh = open(pidfile, 'w')
    proc = subprocess.Popen(cmd, stdout=logfh, stderr=logfh, cwd=chdir)
    pidfh.write(str(proc.pid))
    pidfh.close()


def get_user_name_id(user):
    """
    Get the user id # and name.

    @param user: integer or string containing either the uid #
        or a string username

    @returns a tuple of the user name, user id
    """
    if re.match('\d+', str(user)):
        pass_info = pwd.getpwuid(user)
    else:
        pass_info = pwd.getpwnam(user)

    return pass_info[0], pass_info[2]


def get_group_name_id(group):
    """
    Get the group id # and name

    @param group: integer or string containing either the uid #
        or a string username

    @returns a tuple of group name, group id
    """
    if re.match('\d+', str(group)):
        group_info = grp.getgrgid(group)
    else:
        group_info = grp.getgrnam(group)

    return group_info[0], group_info[2]


def set_group_user(group=None, user=None):
    """
    Set the group and user id if gid or uid is defined.

    @param group: Change the group id the program is run under
    @param user: Change the user id the program is run under
    """
    if group:
        _, gid = get_group_name_id(group)
        os.setgid(gid)
        os.setegid(gid)

    if user:
        username, uid = get_user_name_id(user)
        # Set environment for programs that use those to find running user
        for name in ('LOGNAME', 'USER', 'LNAME', 'USERNAME'):
            os.environ[name] = username
        os.setuid(uid)
        os.seteuid(uid)


def main():
    parser = optparse.OptionParser()
    parser.allow_interspersed_args = False
    parser.add_option('-l', '--logfile', action='store',
                      default=None,
                      help='File to redirect stdout to')
    parser.add_option('-c', '--chdir', action='store',
                      default=None,
                      help='Change to dir before starting the process')
    parser.add_option('-s', '--start-service', action='store_true',
                      default=False,
                      help='Start service')
    parser.add_option('-k', '--stop-service', action='store_true',
                      default=False,
                      help='Stop service')
    parser.add_option('-p', '--pidfile', action='store',
                      default=None,
                      help='Pid file location (Required)')
    parser.add_option('-u', '--chuid', action='store',
                      default=None,
                      help='UID to run process as')
    parser.add_option('-g', '--chgid', action='store',
                      default=None,
                      help='GID to run process as')



    options, args = parser.parse_args()

    if not options.pidfile:
        print 'A pidfile must always be supplied'
        parser.print_help()
        sys.exit(1)

    set_group_user(group=options.chgid, user=options.chuid)
    if options.start_service:
        start_service(args, options.pidfile, options.logfile, options.chdir)
    elif options.stop_service:
        stop_service(options.pidfile)
    else:
        print 'Nothing to do, you must specify to start or stop a service'
        parser.print_help()


if __name__ == '__main__':
    main()
