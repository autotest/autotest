#!/usr/bin/python
"""
Simple crash handling application for autotest

@copyright Red Hat Inc 2009
@author Lucas Meneghel Rodrigues <lmr@redhat.com>
"""
import sys, os, commands, glob, tempfile, shutil, syslog


def get_parent_pid(pid):
    """
    Returns the parent PID for a given PID, converted to an integer.

    @param pid: Process ID.
    """
    try:
        ppid = int(open('/proc/%s/stat' % pid).read().split()[3])
    except:
        # It is not possible to determine the parent because the process
        # already left the process table.
        ppid = 1

    return ppid


def write_to_file(file_path, contents):
    """
    Write contents to a given file path specified. If not specified, the file
    will be created.

    @param file_path: Path to a given file.
    @param contents: File contents.
    """
    file_object = open(file_path, 'w')
    file_object.write(contents)
    file_object.close()


def get_results_dir_list(pid, core_dir_basename):
    """
    Get all valid output directories for the core file and the report. It works
    by inspecting files created by each test on /tmp and verifying if the
    PID of the process that crashed is a child or grandchild of the autotest
    test process. If it can't find any relationship (maybe a daemon that died
    during a test execution), it will write the core file to the debug dirs
    of all tests currently being executed. If there are no active autotest
    tests at a particular moment, it will return a list with ['/tmp'].

    @param pid: PID for the process that generated the core
    @param core_dir_basename: Basename for the directory that will hold both
            the core dump and the crash report.
    """
    pid_dir_dict = {}
    for debugdir_file in glob.glob("/tmp/autotest_results_dir.*"):
        a_pid = os.path.splitext(debugdir_file)[1]
        results_dir = open(debugdir_file).read().strip()
        pid_dir_dict[a_pid] = os.path.join(results_dir, core_dir_basename)

    results_dir_list = []
    while pid > 1:
        if pid in pid_dir_dict:
            results_dir_list.append(pid_dir_dict[pid])
        pid = get_parent_pid(pid)

    return (results_dir_list or
           pid_dir_dict.values() or
           [os.path.join("/tmp", core_dir_basename)])


def get_info_from_core(path):
    """
    Reads a core file and extracts a dictionary with useful core information.
    Right now, the only information extracted is the full executable name.

    @param path: Path to core file.
    """
    # Here we are getting the executable full path in a very inelegant way :(
    # Since the 'right' solution for it is to make a library to get information
    # from core dump files, properly written, I'll leave this as it is for now.
    full_exe_path = commands.getoutput('strings %s | grep "_="' %
                                       path).strip("_=")
    if full_exe_path.startswith("./"):
        pwd = commands.getoutput('strings %s | grep "^PWD="' %
                                 path).strip("PWD=")
        full_exe_path = os.path.join(pwd, full_exe_path.strip("./"))

    return {'core_file': path, 'full_exe_path': full_exe_path}


if __name__ == "__main__":
    syslog.openlog('AutotestCrashHandler', 0, syslog.LOG_DAEMON)
    (crashed_pid, time, uid, signal, hostname, exe) = sys.argv[1:]
    core_name = 'core'
    report_name = 'report'
    core_dir_name = 'crash.%s.%s' % (exe, crashed_pid)
    core_tmp_dir = tempfile.mkdtemp(prefix='core_', dir='/tmp')
    core_tmp_path = os.path.join(core_tmp_dir, core_name)
    gdb_command_path = os.path.join(core_tmp_dir, 'gdb_command')

    try:
        # Get the filtered results dir list
        current_results_dir_list = get_results_dir_list(crashed_pid,
                                                        core_dir_name)

        # Write the core file to the appropriate directory
        # (we are piping it to this script)
        core_file = sys.stdin.read()
        write_to_file(core_tmp_path, core_file)

        # Write a command file for GDB
        gdb_command = 'bt full\n'
        write_to_file(gdb_command_path, gdb_command)

        # Get full command path
        exe_path = get_info_from_core(core_tmp_path)['full_exe_path']

        # Take a backtrace from the running program
        gdb_cmd = 'gdb -e %s -c %s -x %s -n -batch -quiet' % (exe_path,
                                                              core_tmp_path,
                                                              gdb_command_path)
        backtrace = commands.getoutput(gdb_cmd)
        # Sanitize output before passing it to the report
        backtrace = backtrace.decode('utf-8', 'ignore')

        # Composing the format_dict
        format_dict = {}
        format_dict['program'] = exe_path
        format_dict['pid'] = crashed_pid
        format_dict['signal'] = signal
        format_dict['hostname'] = hostname
        format_dict['time'] = time
        format_dict['backtrace'] = backtrace

        report = """Autotest crash report

Program: %(program)s
PID: %(pid)s
Signal: %(signal)s
Hostname: %(hostname)s
Time of the crash: %(time)s
Program backtrace:
%(backtrace)s
""" % format_dict

        syslog.syslog(syslog.LOG_INFO,
                      "Application %s, PID %s crashed" %
                      (exe_path, crashed_pid))

        # Now, for all results dir, let's create the directory if it doesn't
        # exist, and write the core file and the report to it.
        syslog.syslog(syslog.LOG_INFO,
                      "Writing core files and reports to %s" %
                      current_results_dir_list)
        for result_dir in current_results_dir_list:
            if not os.path.isdir(result_dir):
                os.makedirs(result_dir)
            core_path = os.path.join(result_dir, 'core')
            write_to_file(core_path, core_file)
            report_path = os.path.join(result_dir, 'report')
            write_to_file(report_path, report)

    finally:
        # Cleanup temporary directories
        shutil.rmtree(core_tmp_dir)

