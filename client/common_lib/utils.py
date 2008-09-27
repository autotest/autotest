#!/usr/bin/python
#
# Copyright 2008 Google Inc. Released under the GPL v2

import os, pickle, random, re, resource, select, shutil, signal, StringIO
import socket, struct, subprocess, sys, time, textwrap, urllib, urlparse
import warnings
from autotest_lib.client.common_lib import error, barrier

def deprecated(func):
    """This is a decorator which can be used to mark functions as deprecated.
    It will result in a warning being emmitted when the function is used."""
    def new_func(*args, **dargs):
        warnings.warn("Call to deprecated function %s." % func.__name__,
                      category=DeprecationWarning)
        return func(*args, **dargs)
    new_func.__name__ = func.__name__
    new_func.__doc__ = func.__doc__
    new_func.__dict__.update(func.__dict__)
    return new_func


class BgJob(object):
    def __init__(self, command, stdout_tee=None, stderr_tee=None, verbose=True):
        self.command = command
        self.stdout_tee = stdout_tee
        self.stderr_tee = stderr_tee
        self.result = CmdResult(command)
        if verbose:
            print "running: %s" % command
        self.sp = subprocess.Popen(command, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE,
                                   preexec_fn=self._reset_sigpipe, shell=True,
                                   executable="/bin/bash")


    def output_prepare(self, stdout_file=None, stderr_file=None):
        self.stdout_file = stdout_file
        self.stderr_file = stderr_file

    def process_output(self, stdout=True, final_read=False):
        """output_prepare must be called prior to calling this"""
        if stdout:
            pipe, buf, tee = self.sp.stdout, self.stdout_file, self.stdout_tee
        else:
            pipe, buf, tee = self.sp.stderr, self.stderr_file, self.stderr_tee

        if final_read:
            # read in all the data we can from pipe and then stop
            data = []
            while select.select([pipe], [], [], 0)[0]:
                data.append(os.read(pipe.fileno(), 1024))
                if len(data[-1]) == 0:
                    break
            data = "".join(data)
        else:
            # perform a single read
            data = os.read(pipe.fileno(), 1024)
        buf.write(data)
        if tee:
            tee.write(data)
            tee.flush()


    def cleanup(self):
        self.sp.stdout.close()
        self.sp.stderr.close()
        self.result.stdout = self.stdout_file.getvalue()
        self.result.stderr = self.stderr_file.getvalue()


    def _reset_sigpipe(self):
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)


def ip_to_long(ip):
    # !L is a long in network byte order
    return struct.unpack('!L', socket.inet_aton(ip))[0]


def long_to_ip(number):
    # See above comment.
    return socket.inet_ntoa(struct.pack('!L', number))


def create_subnet_mask(bits):
    # ~ does weird things in python...but this does work
    return (1 << 32) - (1 << 32-bits)


def format_ip_with_mask(ip, mask_bits):
    masked_ip = ip_to_long(ip) & create_subnet_mask(mask_bits)
    return "%s/%s" % (long_to_ip(masked_ip), mask_bits)


def get_ip_local_port_range():
    match = re.match(r'\s*(\d+)\s*(\d+)\s*$',
                     read_one_line('/proc/sys/net/ipv4/ip_local_port_range'))
    return (int(match.group(1)), int(match.group(2)))


def set_ip_local_port_range(lower, upper):
    write_one_line('/proc/sys/net/ipv4/ip_local_port_range',
                   '%d %d\n' % (lower, upper))

def read_one_line(filename):
    return open(filename, 'r').readline().rstrip('\n')


def write_one_line(filename, str):
    open(filename, 'w').write(str.rstrip('\n') + '\n')


def read_keyval(path):
    """
    Read a key-value pair format file into a dictionary, and return it.
    Takes either a filename or directory name as input. If it's a
    directory name, we assume you want the file to be called keyval.
    """
    if os.path.isdir(path):
        path = os.path.join(path, 'keyval')
    keyval = {}
    for line in open(path):
        line = re.sub('#.*', '', line).rstrip()
        if not re.search(r'^[-\w]+=', line):
            raise ValueError('Invalid format line: %s' % line)
        key, value = line.split('=', 1)
        if re.search('^\d+$', value):
            value = int(value)
        elif re.search('^(\d+\.)?\d+$', value):
            value = float(value)
        keyval[key] = value
    return keyval


def write_keyval(path, dictionary, type_tag=None):
    """
    Write a key-value pair format file out to a file. This uses append
    mode to open the file, so existing text will not be overwritten or
    reparsed.

    If type_tag is None, then the key must be composed of alphanumeric
    characters (or dashes+underscores). However, if type-tag is not
    null then the keys must also have "{type_tag}" as a suffix. At
    the moment the only valid values of type_tag are "attr" and "perf".
    """
    if os.path.isdir(path):
        path = os.path.join(path, 'keyval')
    keyval = open(path, 'a')

    if type_tag is None:
        key_regex = re.compile(r'^[-\w]+$')
    else:
        if type_tag not in ('attr', 'perf'):
            raise ValueError('Invalid type tag: %s' % type_tag)
        escaped_tag = re.escape(type_tag)
        key_regex = re.compile(r'^[-\w]+\{%s\}$' % escaped_tag)
    try:
        for key, value in dictionary.iteritems():
            if not key_regex.search(key):
                raise ValueError('Invalid key: %s' % key)
            keyval.write('%s=%s\n' % (key, value))
    finally:
        keyval.close()


def is_url(path):
    """Return true if path looks like a URL"""
    # for now, just handle http and ftp
    url_parts = urlparse.urlparse(path)
    return (url_parts[0] in ('http', 'ftp'))


def urlopen(url, data=None, proxies=None, timeout=300):
    """Wrapper to urllib.urlopen with timeout addition."""

    # Save old timeout
    old_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(timeout)
    try:
        return urllib.urlopen(url, data=data, proxies=proxies)
    finally:
        socket.setdefaulttimeout(old_timeout)


def urlretrieve(url, filename=None, reporthook=None, data=None, timeout=300):
    """Wrapper to urllib.urlretrieve with timeout addition."""
    old_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(timeout)
    try:
        return urllib.urlretrieve(url, filename=filename,
                                  reporthook=reporthook, data=data)
    finally:
        socket.setdefaulttimeout(old_timeout)


def get_file(src, dest, permissions=None):
    """Get a file from src, which can be local or a remote URL"""
    if (src == dest):
        return
    if (is_url(src)):
        print 'PWD: ' + os.getcwd()
        print 'Fetching \n\t', src, '\n\t->', dest
        try:
            urllib.urlretrieve(src, dest)
        except IOError, e:
            raise error.AutotestError('Unable to retrieve %s (to %s)'
                                % (src, dest), e)
    else:
        shutil.copyfile(src, dest)
    if permissions:
        os.chmod(dest, permissions)
    return dest


def unmap_url(srcdir, src, destdir='.'):
    """
    Receives either a path to a local file or a URL.
    returns either the path to the local file, or the fetched URL

    unmap_url('/usr/src', 'foo.tar', '/tmp')
                            = '/usr/src/foo.tar'
    unmap_url('/usr/src', 'http://site/file', '/tmp')
                            = '/tmp/file'
                            (after retrieving it)
    """
    if is_url(src):
        url_parts = urlparse.urlparse(src)
        filename = os.path.basename(url_parts[2])
        dest = os.path.join(destdir, filename)
        return get_file(src, dest)
    else:
        return os.path.join(srcdir, src)


def update_version(srcdir, preserve_srcdir, new_version, install,
                   *args, **dargs):
    """
    Make sure srcdir is version new_version

    If not, delete it and install() the new version.

    In the preserve_srcdir case, we just check it's up to date,
    and if not, we rerun install, without removing srcdir
    """
    versionfile = os.path.join(srcdir, '.version')
    install_needed = True

    if os.path.exists(versionfile):
        old_version = pickle.load(open(versionfile))
        if old_version == new_version:
            install_needed = False

    if install_needed:
        if not preserve_srcdir and os.path.exists(srcdir):
            shutil.rmtree(srcdir)
        install(*args, **dargs)
        if os.path.exists(srcdir):
            pickle.dump(new_version, open(versionfile, 'w'))


def run(command, timeout=None, ignore_status=False,
        stdout_tee=None, stderr_tee=None, verbose=True):
    """
    Run a command on the host.

    Args:
            command: the command line string
            timeout: time limit in seconds before attempting to
                    kill the running process. The run() function
                    will take a few seconds longer than 'timeout'
                    to complete if it has to kill the process.
            ignore_status: do not raise an exception, no matter what
                    the exit code of the command is.
            stdout_tee: optional file-like object to which stdout data
                        will be written as it is generated (data will still
                        be stored in result.stdout)
            stderr_tee: likewise for stderr

    Returns:
            a CmdResult object

    Raises:
            CmdError: the exit code of the command
                    execution was not 0
    """
    bg_job = join_bg_jobs((BgJob(command, stdout_tee, stderr_tee, verbose),),
                          timeout)[0]
    if not ignore_status and bg_job.result.exit_status:
        raise error.CmdError(command, bg_job.result,
                             "Command returned non-zero exit status")

    return bg_job.result

def run_parallel(commands, timeout=None, ignore_status=False,
                 stdout_tee=None, stderr_tee=None):
    """Beahves the same as run with the following exceptions:

    - commands is a list of commands to run in parallel.
    - ignore_status toggles whether or not an exception should be raised
      on any error.

    returns a list of CmdResult objects
    """
    bg_jobs = []
    for command in commands:
        bg_jobs.append(BgJob(command, stdout_tee, stderr_tee))

    # Updates objects in bg_jobs list with their process information
    join_bg_jobs(bg_jobs, timeout)

    for bg_job in bg_jobs:
        if not ignore_status and bg_job.result.exit_status:
            raise error.CmdError(command, bg_job.result,
                                 "Command returned non-zero exit status")

    return [bg_job.result for bg_job in bg_jobs]


@deprecated
def run_bg(command):
    """Function deprecated. Please use BgJob class instead."""
    bg_job = BgJob(command)
    return bg_job.sp, bg_job.result


def join_bg_jobs(bg_jobs, timeout=None):
    """Joins the bg_jobs with the current thread.

    Returns the same list of bg_jobs objects that was passed in.
    """
    ret, timeouterr = 0, False
    for bg_job in bg_jobs:
        bg_job.output_prepare(StringIO.StringIO(), StringIO.StringIO())

    try:
        # We are holding ends to stdin, stdout pipes
        # hence we need to be sure to close those fds no mater what
        start_time = time.time()
        timeout_error = _wait_for_commands(bg_jobs, start_time, timeout)

        for bg_job in bg_jobs:
            # Process stdout and stderr
            bg_job.process_output(stdout=True,final_read=True)
            bg_job.process_output(stdout=False,final_read=True)
    finally:
        # close our ends of the pipes to the sp no matter what
        for bg_job in bg_jobs:
            bg_job.cleanup()

    if timeout_error:
        # TODO: This needs to be fixed to better represent what happens when
        # running in parallel. However this is backwards compatable, so it will
        # do for the time being.
        raise error.CmdError(bg_jobs[0].command, bg_jobs[0].result,
                             "Command(s) did not complete within %d seconds"
                             % timeout)


    return bg_jobs


def _wait_for_commands(bg_jobs, start_time, timeout):
    # This returns True if it must return due to a timeout, otherwise False.

    # To check for processes which terminate without producing any output
    # a 1 second timeout is used in select.
    SELECT_TIMEOUT = 1

    select_list = []
    reverse_dict = {}
    for bg_job in bg_jobs:
        select_list.append(bg_job.sp.stdout)
        select_list.append(bg_job.sp.stderr)
        reverse_dict[bg_job.sp.stdout] = (bg_job,True)
        reverse_dict[bg_job.sp.stderr] = (bg_job,False)

    if timeout:
        stop_time = start_time + timeout
        time_left = stop_time - time.time()
    else:
        time_left = None # so that select never times out
    while not timeout or time_left > 0:
        # select will return when stdout is ready (including when it is
        # EOF, that is the process has terminated).
        ready, _, _ = select.select(select_list, [], [], SELECT_TIMEOUT)

        # os.read() has to be used instead of
        # subproc.stdout.read() which will otherwise block
        for fileno in ready:
            bg_job,stdout = reverse_dict[fileno]
            bg_job.process_output(stdout)

        remaining_jobs = [x for x in bg_jobs if x.result.exit_status is None]
        if len(remaining_jobs) == 0:
            return False
        for bg_job in remaining_jobs:
            bg_job.result.exit_status = bg_job.sp.poll()

        if timeout:
            time_left = stop_time - time.time()

    # Kill all processes which did not complete prior to timeout
    for bg_job in [x for x in bg_jobs if x.result.exit_status is None]:
        nuke_subprocess(bg_job.sp)

    return True


def nuke_subprocess(subproc):
    # check if the subprocess is still alive, first
    if subproc.poll() is not None:
        return subproc.poll()

    # the process has not terminated within timeout,
    # kill it via an escalating series of signals.
    signal_queue = [signal.SIGTERM, signal.SIGKILL]
    for sig in signal_queue:
        try:
            os.kill(subproc.pid, sig)
        # The process may have died before we could kill it.
        except OSError:
            pass

        for i in range(5):
            rc = subproc.poll()
            if rc != None:
                return rc
            time.sleep(1)


def nuke_pid(pid):
    # the process has not terminated within timeout,
    # kill it via an escalating series of signals.
    signal_queue = [signal.SIGTERM, signal.SIGKILL]
    for sig in signal_queue:
        try:
            os.kill(pid, sig)

        # The process may have died before we could kill it.
        except OSError:
            pass

        try:
            for i in range(5):
                status = os.waitpid(pid, os.WNOHANG)[0]
                if status == pid:
                    return
                time.sleep(1)

            if status != pid:
                raise error.AutoservRunError('Could not kill %d'
                        % pid, None)

        # the process died before we join it.
        except OSError:
            pass



def system(command, timeout=None, ignore_status=False):
    """This function returns the exit status of command."""
    return run(command, timeout, ignore_status,
               stdout_tee=sys.stdout, stderr_tee=sys.stderr).exit_status


def system_parallel(commands, timeout=None, ignore_status=False):
    """This function returns a list of exit statuses for the respective
    list of commands."""
    return [bg_jobs.exit_status for bg_jobs in
            run_parallel(commands, timeout, ignore_status,
                         stdout_tee=sys.stdout, stderr_tee=sys.stderr)]


def system_output(command, timeout=None, ignore_status=False,
                  retain_output=False):
    if retain_output:
        out = run(command, timeout, ignore_status,
                  stdout_tee=sys.stdout, stderr_tee=sys.stderr).stdout
    else:
        out = run(command, timeout, ignore_status).stdout
    if out[-1:] == '\n': out = out[:-1]
    return out


def system_output_parallel(commands, timeout=None, ignore_status=False,
                           retain_output=False):
    if retain_output:
        out = [bg_job.stdout for bg_job in run_parallel(commands, timeout,
                                                        ignore_status,
                                                        stdout_tee=sys.stdout,
                                                        stderr_tee=sys.stderr)]
    else:
        out = [bg_job.stdout for bg_job in run_parallel(commands, timeout,
                                                        ignore_status)]
    for x in out:
        if out[-1:] == '\n': out = out[:-1]
    return out


def get_cpu_percentage(function, *args, **dargs):
    """Returns a tuple containing the CPU% and return value from function call.

    This function calculates the usage time by taking the difference of
    the user and system times both before and after the function call.
    """
    child_pre = resource.getrusage(resource.RUSAGE_CHILDREN)
    self_pre = resource.getrusage(resource.RUSAGE_SELF)
    start = time.time()
    to_return = function(*args, **dargs)
    elapsed = time.time() - start
    self_post = resource.getrusage(resource.RUSAGE_SELF)
    child_post = resource.getrusage(resource.RUSAGE_CHILDREN)

    # Calculate CPU Percentage
    s_user, s_system = [a - b for a, b in zip(self_post, self_pre)[:2]]
    c_user, c_system = [a - b for a, b in zip(child_post, child_pre)[:2]]
    cpu_percent = (s_user + c_user + s_system + c_system) / elapsed

    return cpu_percent, to_return


"""
This function is used when there is a need to run more than one
job simultaneously starting exactly at the same time. It basically returns
a modified control file (containing the synchronization code prepended)
whenever it is ready to run the control file. The synchronization
is done using barriers to make sure that the jobs start at the same time.

Here is how the synchronization is done to make sure that the tests
start at exactly the same time on the client.
sc_bar is a server barrier and s_bar, c_bar are the normal barriers

                  Job1              Job2         ......      JobN
 Server:   |                        sc_bar
 Server:   |                        s_bar        ......      s_bar
 Server:   |      at.run()         at.run()      ......      at.run()
 ----------|------------------------------------------------------
 Client    |      sc_bar
 Client    |      c_bar             c_bar        ......      c_bar
 Client    |    <run test>         <run test>    ......     <run test>


PARAMS:
   control_file : The control file which to which the above synchronization
                  code would be prepended to
   host_name    : The host name on which the job is going to run
   host_num (non negative) : A number to identify the machine so that we have
                  different sets of s_bar_ports for each of the machines.
   instance     : The number of the job
   num_jobs     : Total number of jobs that are going to run in parallel with
                  this job starting at the same time
   port_base    : Port number that is used to derive the actual barrier ports.

RETURN VALUE:
    The modified control file.

"""
def get_sync_control_file(control, host_name, host_num,
                          instance, num_jobs, port_base=63100):
    sc_bar_port = port_base
    c_bar_port = port_base
    if host_num < 0:
        print "Please provide a non negative number for the host"
        return None
    s_bar_port = port_base + 1 + host_num # The set of s_bar_ports are
                                          # the same for a given machine

    sc_bar_timeout = 180
    s_bar_timeout = c_bar_timeout = 120

    # The barrier code snippet is prepended into the conrol file
    # dynamically before at.run() is called finally.
    control_new = []

    # jobid is the unique name used to identify the processes
    # trying to reach the barriers
    jobid = "%s#%d" % (host_name, instance)

    rendv = []
    # rendvstr is a temp holder for the rendezvous list of the processes
    for n in range(num_jobs):
        rendv.append("'%s#%d'" % (host_name, n))
    rendvstr = ",".join(rendv)

    if instance == 0:
        # Do the setup and wait at the server barrier
        # Clean up the tmp and the control dirs for the first instance
        control_new.append('if os.path.exists(job.tmpdir):')
        control_new.append("\t system('umount -f %s > /dev/null"
                           "2> /dev/null' % job.tmpdir,"
                           "ignore_status=True)")
        control_new.append("\t system('rm -rf ' + job.tmpdir)")
        control_new.append(
            'b0 = job.barrier("%s", "sc_bar", %d, port=%d)'
            % (jobid, sc_bar_timeout, sc_bar_port))
        control_new.append(
        'b0.rendevous_servers("PARALLEL_MASTER", "%s")'
         % jobid)

    elif instance == 1:
        # Wait at the server barrier to wait for instance=0
        # process to complete setup
        b0 = barrier.barrier("PARALLEL_MASTER", "sc_bar", sc_bar_timeout,
                     port=sc_bar_port)
        b0.rendevous_servers("PARALLEL_MASTER", jobid)

        if(num_jobs > 2):
            b1 = barrier.barrier(jobid, "s_bar", s_bar_timeout,
                         port=s_bar_port)
            b1.rendevous(rendvstr)

    else:
        # For the rest of the clients
        b2 = barrier.barrier(jobid, "s_bar", s_bar_timeout, port=s_bar_port)
        b2.rendevous(rendvstr)

    # Client side barrier for all the tests to start at the same time
    control_new.append('b1 = job.barrier("%s", "c_bar", %d, port=%d)'
                    % (jobid, c_bar_timeout, c_bar_port))
    control_new.append("b1.rendevous(%s)" % rendvstr)

    # Stick in the rest of the control file
    control_new.append(control)

    return "\n".join(control_new)


def get_arch(run_function=run):
    """
    Get the hardware architecture of the machine.
    run_function is used to execute the commands. It defaults to
    utils.run() but a custom method (if provided) should be of the
    same schema as utils.run. It should return a CmdResult object and
    throw a CmdError exception.
    """
    arch = run_function('/bin/uname -m').stdout.rstrip()
    if re.match(r'i\d86$', arch):
        arch = 'i386'
    return arch


class CmdResult(object):
    """
    Command execution result.

    command:     String containing the command line itself
    exit_status: Integer exit code of the process
    stdout:      String containing stdout of the process
    stderr:      String containing stderr of the process
    duration:    Elapsed wall clock time running the process
    """


    def __init__(self, command=None, stdout="", stderr="",
                 exit_status=None, duration=0):
        self.command = command
        self.exit_status = exit_status
        self.stdout = stdout
        self.stderr = stderr
        self.duration = duration


    def __repr__(self):
        wrapper = textwrap.TextWrapper(width = 78,
                                       initial_indent="\n    ",
                                       subsequent_indent="    ")

        stdout = self.stdout.rstrip()
        if stdout:
            stdout = "\nstdout:\n%s" % stdout

        stderr = self.stderr.rstrip()
        if stderr:
            stderr = "\nstderr:\n%s" % stderr

        return ("* Command: %s\n"
                "Exit status: %s\n"
                "Duration: %s\n"
                "%s"
                "%s"
                % (wrapper.fill(self.command), self.exit_status,
                self.duration, stdout, stderr))


class run_randomly:
    def __init__(self, run_sequentially=False):
        # Run sequentially is for debugging control files
        self.test_list = []
        self.run_sequentially = run_sequentially


    def add(self, *args, **dargs):
        test = (args, dargs)
        self.test_list.append(test)


    def run(self, fn):
        while self.test_list:
            test_index = random.randint(0, len(self.test_list)-1)
            if self.run_sequentially:
                test_index = 0
            (args, dargs) = self.test_list.pop(test_index)
            fn(*args, **dargs)
