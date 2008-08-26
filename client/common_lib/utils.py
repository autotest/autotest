#!/usr/bin/python
#
# Copyright 2008 Google Inc. Released under the GPL v2

import os, pickle, random, re, select, shutil, signal, StringIO, subprocess
import socket, sys, time, textwrap, urllib, urlparse, struct
from autotest_lib.client.common_lib import error, barrier


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
        stdout_tee=None, stderr_tee=None):
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
    return join_bg_job(run_bg(command), command, timeout, ignore_status,
                       stdout_tee, stderr_tee)


def run_bg(command):
    """Run the command in a subprocess and return the subprocess."""
    result = CmdResult(command)
    def reset_sigpipe():
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    print "running: %s" % command
    sp = subprocess.Popen(command, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, preexec_fn=reset_sigpipe,
                          shell=True, executable="/bin/bash")
    return sp, result


def join_bg_job(bg_job, command, timeout=None, ignore_status=False,
        stdout_tee=None, stderr_tee=None):
    """Join the subprocess with the current thread. See run description."""
    sp, result = bg_job
    stdout_file = StringIO.StringIO()
    stderr_file = StringIO.StringIO()
    (ret, timeouterr) = (0, False)

    try:
        # We are holding ends to stdin, stdout pipes
        # hence we need to be sure to close those fds no mater what
        start_time = time.time()
        (ret, timeouterr) = _wait_for_command(sp, start_time,
                                timeout, stdout_file, stderr_file,
                                stdout_tee, stderr_tee)
        result.exit_status = ret
        result.duration = time.time() - start_time
        # don't use os.read now, so we get all the rest of the output
        _process_output(sp.stdout, stdout_file, stdout_tee, final_read=True)
        _process_output(sp.stderr, stderr_file, stderr_tee, final_read=True)
    finally:
        # close our ends of the pipes to the sp no matter what
        sp.stdout.close()
        sp.stderr.close()

    result.stdout = stdout_file.getvalue()
    result.stderr = stderr_file.getvalue()

    if result.exit_status != 0:
        if timeouterr:
            raise error.CmdError(command, result, "Command did not "
                                 "complete within %d seconds" % timeout)
        elif not ignore_status:
            raise error.CmdError(command, result,
                                 "Command returned non-zero exit status")

    return result

# this returns a tuple with the return code and a flag to specify if the error
# is due to the process not terminating within timeout
def _wait_for_command(subproc, start_time, timeout, stdout_file, stderr_file,
                      stdout_tee, stderr_tee):
    if timeout:
        stop_time = start_time + timeout
        time_left = stop_time - time.time()
    else:
        time_left = None # so that select never times out
    while not timeout or time_left > 0:
        # select will return when stdout is ready (including when it is
        # EOF, that is the process has terminated).
        ready, _, _ = select.select([subproc.stdout, subproc.stderr],
                                     [], [], time_left)
        # os.read() has to be used instead of
        # subproc.stdout.read() which will otherwise block
        if subproc.stdout in ready:
            _process_output(subproc.stdout, stdout_file, stdout_tee)
        if subproc.stderr in ready:
            _process_output(subproc.stderr, stderr_file, stderr_tee)

        exit_status_indication = subproc.poll()

        if exit_status_indication is not None:
            return (exit_status_indication, False)

        if timeout:
            time_left = stop_time - time.time()

    # the process has not terminated within timeout,
    # kill it via an escalating series of signals.
    if exit_status_indication is None:
        exit_status_indication = nuke_subprocess(subproc)

    return (exit_status_indication, True)


def nuke_subprocess(subproc):
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


def _process_output(pipe, fbuffer, teefile=None, final_read=False):
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
    fbuffer.write(data)
    if teefile:
        teefile.write(data)
        teefile.flush()


def system(command, timeout=None, ignore_status=False):
    return run(command, timeout, ignore_status,
            stdout_tee=sys.stdout, stderr_tee=sys.stderr).exit_status


def system_output(command, timeout=None, ignore_status=False,
                  retain_output=False):
    if retain_output:
        out = run(command, timeout, ignore_status,
                  stdout_tee=sys.stdout, stderr_tee=sys.stderr).stdout
    else:
        out = run(command, timeout, ignore_status).stdout
    if out[-1:] == '\n': out = out[:-1]
    return out

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
