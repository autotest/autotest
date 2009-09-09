#
# Copyright 2008 Google Inc. Released under the GPL v2

import os, pickle, random, re, resource, select, shutil, signal, StringIO
import socket, struct, subprocess, sys, time, textwrap, urlparse
import warnings, smtplib, logging, urllib2
from autotest_lib.client.common_lib import error, barrier, logging_manager

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


class _NullStream(object):
    def write(self, data):
        pass


    def flush(self):
        pass


TEE_TO_LOGS = object()
_the_null_stream = _NullStream()

DEFAULT_STDOUT_LEVEL = logging.DEBUG
DEFAULT_STDERR_LEVEL = logging.ERROR

def get_stream_tee_file(stream, level):
    if stream is None:
        return _the_null_stream
    if stream is TEE_TO_LOGS:
        return logging_manager.LoggingFile(level=level)
    return stream


class BgJob(object):
    def __init__(self, command, stdout_tee=None, stderr_tee=None, verbose=True,
                 stdin=None, stderr_level=DEFAULT_STDERR_LEVEL):
        self.command = command
        self.stdout_tee = get_stream_tee_file(stdout_tee, DEFAULT_STDOUT_LEVEL)
        self.stderr_tee = get_stream_tee_file(stderr_tee, stderr_level)
        self.result = CmdResult(command)
        if verbose:
            logging.debug("Running '%s'" % command)
        self.sp = subprocess.Popen(command, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE,
                                   preexec_fn=self._reset_sigpipe, shell=True,
                                   executable="/bin/bash",
                                   stdin=stdin)


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
        tee.write(data)


    def cleanup(self):
        self.stdout_tee.flush()
        self.stderr_tee.flush()
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
    return (1 << 32) - (1 << 32-bits)


def format_ip_with_mask(ip, mask_bits):
    masked_ip = ip_to_long(ip) & create_subnet_mask(mask_bits)
    return "%s/%s" % (long_to_ip(masked_ip), mask_bits)


def normalize_hostname(alias):
    ip = socket.gethostbyname(alias)
    return socket.gethostbyaddr(ip)[0]


def get_ip_local_port_range():
    match = re.match(r'\s*(\d+)\s*(\d+)\s*$',
                     read_one_line('/proc/sys/net/ipv4/ip_local_port_range'))
    return (int(match.group(1)), int(match.group(2)))


def set_ip_local_port_range(lower, upper):
    write_one_line('/proc/sys/net/ipv4/ip_local_port_range',
                   '%d %d\n' % (lower, upper))



def send_email(mail_from, mail_to, subject, body):
    """
    Sends an email via smtp

    mail_from: string with email address of sender
    mail_to: string or list with email address(es) of recipients
    subject: string with subject of email
    body: (multi-line) string with body of email
    """
    if isinstance(mail_to, str):
        mail_to = [mail_to]
    msg = "From: %s\nTo: %s\nSubject: %s\n\n%s" % (mail_from, ','.join(mail_to),
                                                   subject, body)
    try:
        mailer = smtplib.SMTP('localhost')
        try:
            mailer.sendmail(mail_from, mail_to, msg)
        finally:
            mailer.quit()
    except Exception, e:
        # Emails are non-critical, not errors, but don't raise them
        print "Sending email failed. Reason: %s" % repr(e)


def read_one_line(filename):
    return open(filename, 'r').readline().rstrip('\n')


def write_one_line(filename, line):
    open_write_close(filename, line.rstrip('\n') + '\n')


def open_write_close(filename, data):
    f = open(filename, 'w')
    try:
        f.write(data)
    finally:
        f.close()


def read_keyval(path):
    """
    Read a key-value pair format file into a dictionary, and return it.
    Takes either a filename or directory name as input. If it's a
    directory name, we assume you want the file to be called keyval.
    """
    if os.path.isdir(path):
        path = os.path.join(path, 'keyval')
    keyval = {}
    if os.path.exists(path):
        for line in open(path):
            line = re.sub('#.*', '', line).rstrip()
            if not re.search(r'^[-\.\w]+=', line):
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
        key_regex = re.compile(r'^[-\.\w]+$')
    else:
        if type_tag not in ('attr', 'perf'):
            raise ValueError('Invalid type tag: %s' % type_tag)
        escaped_tag = re.escape(type_tag)
        key_regex = re.compile(r'^[-\.\w]+\{%s\}$' % escaped_tag)
    try:
        for key in sorted(dictionary.keys()):
            if not key_regex.search(key):
                raise ValueError('Invalid key: %s' % key)
            keyval.write('%s=%s\n' % (key, dictionary[key]))
    finally:
        keyval.close()


def is_url(path):
    """Return true if path looks like a URL"""
    # for now, just handle http and ftp
    url_parts = urlparse.urlparse(path)
    return (url_parts[0] in ('http', 'ftp'))


def urlopen(url, data=None, timeout=5):
    """Wrapper to urllib2.urlopen with timeout addition."""

    # Save old timeout
    old_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(timeout)
    try:
        return urllib2.urlopen(url, data=data)
    finally:
        socket.setdefaulttimeout(old_timeout)


def urlretrieve(url, filename, data=None, timeout=300):
    """Retrieve a file from given url."""
    logging.debug('Fetching %s -> %s', url, filename)

    src_file = urlopen(url, data=data, timeout=timeout)
    try:
        dest_file = open(filename, 'wb')
        try:
            shutil.copyfileobj(src_file, dest_file)
        finally:
            dest_file.close()
    finally:
        src_file.close()


def get_file(src, dest, permissions=None):
    """Get a file from src, which can be local or a remote URL"""
    if src == dest:
        return

    if is_url(src):
        urlretrieve(src, dest)
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


def get_stderr_level(stderr_is_expected):
    if stderr_is_expected:
        return DEFAULT_STDOUT_LEVEL
    return DEFAULT_STDERR_LEVEL


def run(command, timeout=None, ignore_status=False,
        stdout_tee=None, stderr_tee=None, verbose=True, stdin=None,
        stderr_is_expected=None):
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
            verbose: if True, log the command being run
            stdin: stdin to pass to the executed process

    Returns:
            a CmdResult object

    Raises:
            CmdError: the exit code of the command
                    execution was not 0
    """
    if stderr_is_expected is None:
        stderr_is_expected = ignore_status
    bg_job = join_bg_jobs(
        (BgJob(command, stdout_tee, stderr_tee, verbose, stdin=stdin,
               stderr_level=get_stderr_level(stderr_is_expected)),),
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
        bg_jobs.append(BgJob(command, stdout_tee, stderr_tee,
                             stderr_level=get_stderr_level(ignore_status)))

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
    ret, timeout_error = 0, False
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
        print '* Warning: run process timeout (%s) fired' % timeout
        nuke_subprocess(bg_job.sp)
        bg_job.result.exit_status = bg_job.sp.poll()

    return True


def pid_is_alive(pid):
    """
    True if process pid exists and is not yet stuck in Zombie state.
    Zombies are impossible to move between cgroups, etc.
    pid can be integer, or text of integer.
    """
    path = '/proc/%s/stat' % pid

    try:
        stat = read_one_line(path)
    except IOError:
        if not os.path.exists(path):
            # file went away
            return False
        raise

    return stat.split()[2] != 'Z'


def signal_pid(pid, sig):
    """
    Sends a signal to a process id. Returns True if the process terminated
    successfully, False otherwise.
    """
    try:
        os.kill(pid, sig)
    except OSError:
        # The process may have died before we could kill it.
        pass

    for i in range(5):
        if not pid_is_alive(pid):
            return True
        time.sleep(1)

    # The process is still alive
    return False


def nuke_subprocess(subproc):
    # check if the subprocess is still alive, first
    if subproc.poll() is not None:
        return subproc.poll()

    # the process has not terminated within timeout,
    # kill it via an escalating series of signals.
    signal_queue = [signal.SIGTERM, signal.SIGKILL]
    for sig in signal_queue:
        signal_pid(subproc.pid, sig)
        if subproc.poll() is not None:
            return subproc.poll()


def nuke_pid(pid):
    # the process has not terminated within timeout,
    # kill it via an escalating series of signals.
    signal_queue = [signal.SIGTERM, signal.SIGKILL]
    for sig in signal_queue:
        if signal_pid(pid, sig):
            return

    # no signal successfully terminated the process
    raise error.AutoservRunError('Could not kill %d' % pid, None)


def system(command, timeout=None, ignore_status=False):
    """This function returns the exit status of command."""
    return run(command, timeout=timeout, ignore_status=ignore_status,
               stdout_tee=TEE_TO_LOGS, stderr_tee=TEE_TO_LOGS).exit_status


def system_parallel(commands, timeout=None, ignore_status=False):
    """This function returns a list of exit statuses for the respective
    list of commands."""
    return [bg_jobs.exit_status for bg_jobs in
            run_parallel(commands, timeout=timeout, ignore_status=ignore_status,
                         stdout_tee=TEE_TO_LOGS, stderr_tee=TEE_TO_LOGS)]


def system_output(command, timeout=None, ignore_status=False,
                  retain_output=False):
    if retain_output:
        out = run(command, timeout=timeout, ignore_status=ignore_status,
                  stdout_tee=TEE_TO_LOGS, stderr_tee=TEE_TO_LOGS).stdout
    else:
        out = run(command, timeout=timeout, ignore_status=ignore_status).stdout
    if out[-1:] == '\n': out = out[:-1]
    return out


def system_output_parallel(commands, timeout=None, ignore_status=False,
                           retain_output=False):
    if retain_output:
        out = [bg_job.stdout for bg_job
               in run_parallel(commands, timeout=timeout,
                               ignore_status=ignore_status,
                               stdout_tee=TEE_TO_LOGS, stderr_tee=TEE_TO_LOGS)]
    else:
        out = [bg_job.stdout for bg_job in run_parallel(commands,
                                  timeout=timeout, ignore_status=ignore_status)]
    for x in out:
        if out[-1:] == '\n': out = out[:-1]
    return out


def strip_unicode(input):
    if type(input) == list:
        return [strip_unicode(i) for i in input]
    elif type(input) == dict:
        output = {}
        for key in input.keys():
            output[str(key)] = strip_unicode(input[key])
        return output
    elif type(input) == unicode:
        return str(input)
    else:
        return input


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
        'b0.rendezvous_servers("PARALLEL_MASTER", "%s")'
         % jobid)

    elif instance == 1:
        # Wait at the server barrier to wait for instance=0
        # process to complete setup
        b0 = barrier.barrier("PARALLEL_MASTER", "sc_bar", sc_bar_timeout,
                     port=sc_bar_port)
        b0.rendezvous_servers("PARALLEL_MASTER", jobid)

        if(num_jobs > 2):
            b1 = barrier.barrier(jobid, "s_bar", s_bar_timeout,
                         port=s_bar_port)
            b1.rendezvous(rendvstr)

    else:
        # For the rest of the clients
        b2 = barrier.barrier(jobid, "s_bar", s_bar_timeout, port=s_bar_port)
        b2.rendezvous(rendvstr)

    # Client side barrier for all the tests to start at the same time
    control_new.append('b1 = job.barrier("%s", "c_bar", %d, port=%d)'
                    % (jobid, c_bar_timeout, c_bar_port))
    control_new.append("b1.rendezvous(%s)" % rendvstr)

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


def get_num_logical_cpus_per_socket(run_function=run):
    """
    Get the number of cores (including hyperthreading) per cpu.
    run_function is used to execute the commands. It defaults to
    utils.run() but a custom method (if provided) should be of the
    same schema as utils.run. It should return a CmdResult object and
    throw a CmdError exception.
    """
    siblings = run_function('grep "^siblings" /proc/cpuinfo').stdout.rstrip()
    num_siblings = map(int,
                       re.findall(r'^siblings\s*:\s*(\d+)\s*$',
                                  siblings, re.M))
    if len(num_siblings) == 0:
        raise error.TestError('Unable to find siblings info in /proc/cpuinfo')
    if min(num_siblings) != max(num_siblings):
        raise error.TestError('Number of siblings differ %r' %
                              num_siblings)
    return num_siblings[0]


def merge_trees(src, dest):
    """
    Merges a source directory tree at 'src' into a destination tree at
    'dest'. If a path is a file in both trees than the file in the source
    tree is APPENDED to the one in the destination tree. If a path is
    a directory in both trees then the directories are recursively merged
    with this function. In any other case, the function will skip the
    paths that cannot be merged (instead of failing).
    """
    if not os.path.exists(src):
        return # exists only in dest
    elif not os.path.exists(dest):
        if os.path.isfile(src):
            shutil.copy2(src, dest) # file only in src
        else:
            shutil.copytree(src, dest, symlinks=True) # dir only in src
        return
    elif os.path.isfile(src) and os.path.isfile(dest):
        # src & dest are files in both trees, append src to dest
        destfile = open(dest, "a")
        try:
            srcfile = open(src)
            try:
                destfile.write(srcfile.read())
            finally:
                srcfile.close()
        finally:
            destfile.close()
    elif os.path.isdir(src) and os.path.isdir(dest):
        # src & dest are directories in both trees, so recursively merge
        for name in os.listdir(src):
            merge_trees(os.path.join(src, name), os.path.join(dest, name))
    else:
        # src & dest both exist, but are incompatible
        return


class CmdResult(object):
    """
    Command execution result.

    command:     String containing the command line itself
    exit_status: Integer exit code of the process
    stdout:      String containing stdout of the process
    stderr:      String containing stderr of the process
    duration:    Elapsed wall clock time running the process
    """


    def __init__(self, command="", stdout="", stderr="",
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


def import_site_module(path, module, dummy=None, modulefile=None):
    """
    Try to import the site specific module if it exists.

    @param path full filename of the source file calling this (ie __file__)
    @param module full module name
    @param dummy dummy value to return in case there is no symbol to import
    @param modulefile module filename

    @return site specific module or dummy

    @raises ImportError if the site file exists but imports fails
    """
    short_module = module[module.rfind(".") + 1:]

    if not modulefile:
        modulefile = short_module + ".py"

    if os.path.exists(os.path.join(os.path.dirname(path), modulefile)):
        return __import__(module, {}, {}, [short_module])
    return dummy


def import_site_symbol(path, module, name, dummy=None, modulefile=None):
    """
    Try to import site specific symbol from site specific file if it exists

    @param path full filename of the source file calling this (ie __file__)
    @param module full module name
    @param name symbol name to be imported from the site file
    @param dummy dummy value to return in case there is no symbol to import
    @param modulefile module filename

    @return site specific symbol or dummy

    @raises ImportError if the site file exists but imports fails
    """
    module = import_site_module(path, module, modulefile=modulefile)
    if not module:
        return dummy

    # special unique value to tell us if the symbol can't be imported
    cant_import = object()

    obj = getattr(module, name, cant_import)
    if obj is cant_import:
        logging.error("unable to import site symbol '%s', using non-site "
                      "implementation", name)
        return dummy

    return obj


def import_site_class(path, module, classname, baseclass, modulefile=None):
    """
    Try to import site specific class from site specific file if it exists

    Args:
        path: full filename of the source file calling this (ie __file__)
        module: full module name
        classname: class name to be loaded from site file
        baseclass: base class object to return when no site file present or
            to mixin when site class exists but is not inherited from baseclass
        modulefile: module filename

    Returns: baseclass if site specific class does not exist, the site specific
        class if it exists and is inherited from baseclass or a mixin of the
        site specific class and baseclass when the site specific class exists
        and is not inherited from baseclass

    Raises: ImportError if the site file exists but imports fails
    """

    res = import_site_symbol(path, module, classname, None, modulefile)
    if res:
        if not issubclass(res, baseclass):
            # if not a subclass of baseclass then mix in baseclass with the
            # site specific class object and return the result
            res = type(classname, (res, baseclass), {})
    else:
        res = baseclass

    return res


def import_site_function(path, module, funcname, dummy, modulefile=None):
    """
    Try to import site specific function from site specific file if it exists

    Args:
        path: full filename of the source file calling this (ie __file__)
        module: full module name
        funcname: function name to be imported from site file
        dummy: dummy function to return in case there is no function to import
        modulefile: module filename

    Returns: site specific function object or dummy

    Raises: ImportError if the site file exists but imports fails
    """

    return import_site_symbol(path, module, funcname, dummy, modulefile)


def _get_pid_path(program_name):
    my_path = os.path.dirname(__file__)
    return os.path.abspath(os.path.join(my_path, "..", "..",
                                        "%s.pid" % program_name))


def write_pid(program_name):
    """
    Try to drop <program_name>.pid in the main autotest directory.

    Args:
      program_name: prefix for file name
    """
    pidfile = open(_get_pid_path(program_name), "w")
    try:
        pidfile.write("%s\n" % os.getpid())
    finally:
        pidfile.close()


def delete_pid_file_if_exists(program_name):
    """
    Tries to remove <program_name>.pid from the main autotest directory.
    """
    pidfile_path = _get_pid_path(program_name)

    try:
        os.remove(pidfile_path)
    except OSError:
        if not os.path.exists(pidfile_path):
            return
        raise


def get_pid_from_file(program_name):
    """
    Reads the pid from <program_name>.pid in the autotest directory.

    @param program_name the name of the program
    @return the pid if the file exists, None otherwise.
    """
    pidfile_path = _get_pid_path(program_name)
    if not os.path.exists(pidfile_path):
        return None

    pidfile = open(_get_pid_path(program_name), 'r')

    try:
        try:
            pid = int(pidfile.readline())
        except IOError:
            if not os.path.exists(pidfile_path):
                return None
            raise
    finally:
        pidfile.close()

    return pid


def program_is_alive(program_name):
    """
    Checks if the process is alive and not in Zombie state.

    @param program_name the name of the program
    @return True if still alive, False otherwise
    """
    pid = get_pid_from_file(program_name)
    if pid is None:
        return False
    return pid_is_alive(pid)


def signal_program(program_name, sig=signal.SIGTERM):
    """
    Sends a signal to the process listed in <program_name>.pid

    @param program_name the name of the program
    @param sig signal to send
    """
    pid = get_pid_from_file(program_name)
    if pid:
        signal_pid(pid, sig)


def get_relative_path(path, reference):
    """Given 2 absolute paths "path" and "reference", compute the path of
    "path" as relative to the directory "reference".

    @param path the absolute path to convert to a relative path
    @param reference an absolute directory path to which the relative
        path will be computed
    """
    # normalize the paths (remove double slashes, etc)
    assert(os.path.isabs(path))
    assert(os.path.isabs(reference))

    path = os.path.normpath(path)
    reference = os.path.normpath(reference)

    # we could use os.path.split() but it splits from the end
    path_list = path.split(os.path.sep)[1:]
    ref_list = reference.split(os.path.sep)[1:]

    # find the longest leading common path
    for i in xrange(min(len(path_list), len(ref_list))):
        if path_list[i] != ref_list[i]:
            # decrement i so when exiting this loop either by no match or by
            # end of range we are one step behind
            i -= 1
            break
    i += 1
    # drop the common part of the paths, not interested in that anymore
    del path_list[:i]

    # for each uncommon component in the reference prepend a ".."
    path_list[:0] = ['..'] * (len(ref_list) - i)

    return os.path.join(*path_list)


def sh_escape(command):
    """
    Escape special characters from a command so that it can be passed
    as a double quoted (" ") string in a (ba)sh command.

    Args:
            command: the command string to escape.

    Returns:
            The escaped command string. The required englobing double
            quotes are NOT added and so should be added at some point by
            the caller.

    See also: http://www.tldp.org/LDP/abs/html/escapingsection.html
    """
    command = command.replace("\\", "\\\\")
    command = command.replace("$", r'\$')
    command = command.replace('"', r'\"')
    command = command.replace('`', r'\`')
    return command
