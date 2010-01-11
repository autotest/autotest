#!/usr/bin/python
"""Service launcher that creates pidfiles and can redirect output to a file."""
import subprocess, sys, os, optparse, signal, pwd


def stop_service(pidfile):
    """Read the first line of a file for an integer that should refer to a pid,
       send a SIGTERM to that pid #.
       @param pidfile: file to read for the process id number
    """
    pidfh = open(pidfile)
    pid = int(pidfh.readline())
    os.kill(pid, signal.SIGTERM)


def start_service(cmd, pidfile, logfile=os.devnull, chdir=None, chuid=None):
    """Start cmd in the background and write the pid to pidfile.
       @param cmd: command to run with arguments
       @param pidfile: pidfile to write the pid to
       @param logfile: file to write stderr/stdout to
       @param chdir: Directory to change to before starting the application
       @param chuid: Change the user id the program is run under
    """
    if chuid:
        # Set environment for programs that use those to find running user
        for name in ('LOGNAME', 'USER', 'LNAME', 'USERNAME'):
            os.environ[name] = chuid
        uid = pwd.getpwnam(chuid)[2]
        os.setuid(uid)
        os.seteuid(uid)
    logfh = open(logfile, 'a')
    pidfh = open(pidfile, 'w')
    proc = subprocess.Popen(cmd, stdout=logfh, stderr=logfh, cwd=chdir)
    pidfh.write(str(proc.pid))
    pidfh.close()


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



    options, args = parser.parse_args()

    if not options.pidfile:
        print 'A pidfile must always be supplied'
        parser.print_help()
        sys.exit(1)

    if options.start_service:
        start_service(args, options.pidfile, options.logfile, options.chdir,
                      options.chuid)
    elif options.stop_service:
        stop_service(options.pidfile)
    else:
        print 'Nothing to do, you must specify to start or stop a service'
        parser.print_help()


if __name__ == '__main__':
    main()
