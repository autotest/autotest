"""
Convenience functions for use by tests or whomever.

NOTE: this is a mixin library that pulls in functions from several places
Note carefully what the precendece order is

There's no really good way to do this, as this isn't a class we can do
inheritance with, just a collection of static methods.
"""

#
# Copyright 2008 Google Inc. Released under the GPL v2

import StringIO
import glob
import logging
import os
import pickle
import random
import re
import resource
import select
import shutil
import signal
import socket
import string
import struct
import subprocess
import sys
import tarfile
import textwrap
import time
import traceback
import urllib2
import urlparse
import warnings
from threading import Thread, Event, Lock

try:
    import hashlib
except ImportError:
    import md5
    import sha
from autotest.client.shared import error, logging_manager
from autotest.client.shared import progressbar
from autotest.client.shared.settings import settings
from autotest.client import os_dep
import commands
import fcntl
import getpass


def deprecated(func):
    """This is a decorator which can be used to mark functions as deprecated.
    It will result in a warning being emitted when the function is used."""
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

# prefixes for logging stdout/stderr of commands
STDOUT_PREFIX = '[stdout] '
STDERR_PREFIX = '[stderr] '


def get_stream_tee_file(stream, level, prefix=''):
    if stream is None:
        return _the_null_stream
    if stream is TEE_TO_LOGS:
        return logging_manager.LoggingFile(level=level, prefix=prefix)
    return stream


class BgJob(object):

    def __init__(self, command, stdout_tee=None, stderr_tee=None, verbose=True,
                 stdin=None, stderr_level=DEFAULT_STDERR_LEVEL,
                 close_fds=False):
        self.command = command
        self.stdout_tee = get_stream_tee_file(stdout_tee, DEFAULT_STDOUT_LEVEL,
                                              prefix=STDOUT_PREFIX)
        self.stderr_tee = get_stream_tee_file(stderr_tee, stderr_level,
                                              prefix=STDERR_PREFIX)
        self.result = CmdResult(command)

        # allow for easy stdin input by string, we'll let subprocess create
        # a pipe for stdin input and we'll write to it in the wait loop
        if isinstance(stdin, basestring):
            self.string_stdin = stdin
            stdin = subprocess.PIPE
        else:
            self.string_stdin = None

        if verbose:
            logging.debug("Running '%s'" % command)
        # Ok, bash is nice and everything, but we might face occasions where
        # it is not available. Just do the right thing and point to /bin/sh.
        shell = '/bin/bash'
        if not os.path.isfile(shell):
            shell = '/bin/sh'
        self.sp = subprocess.Popen(command, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE,
                                   preexec_fn=self._reset_sigpipe,
                                   close_fds=close_fds,
                                   shell=True,
                                   executable=shell,
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


class AsyncJob(BgJob):

    def __init__(self, command, stdout_tee=None, stderr_tee=None, verbose=True,
                 stdin=None, stderr_level=DEFAULT_STDERR_LEVEL, kill_func=None,
                 close_fds=False):
        super(AsyncJob, self).__init__(command, stdout_tee=stdout_tee,
                                       stderr_tee=stderr_tee, verbose=verbose, stdin=stdin,
                                       stderr_level=stderr_level, close_fds=close_fds)

        # start time for CmdResult
        self.start_time = time.time()

        if kill_func is None:
            self.kill_func = self._kill_self_process
        else:
            self.kill_func = kill_func

        if self.string_stdin:
            self.stdin_lock = Lock()
            string_stdin = self.string_stdin
            # replace with None so that _wait_for_commands will not try to re-write it
            self.string_stdin = None
            self.stdin_thread = Thread(target=AsyncJob._stdin_string_drainer, name=("%s-stdin" % command),
                                       args=(string_stdin, self.sp.stdin))
            self.stdin_thread.daemon = True
            self.stdin_thread.start()

        self.stdout_lock = Lock()
        self.stdout_file = StringIO.StringIO()
        self.stdout_thread = Thread(target=AsyncJob._fd_drainer, name=("%s-stdout" % command),
                                    args=(self.sp.stdout, [self.stdout_file, self.stdout_tee],
                                          self.stdout_lock))
        self.stdout_thread.daemon = True

        self.stderr_lock = Lock()
        self.stderr_file = StringIO.StringIO()
        self.stderr_thread = Thread(target=AsyncJob._fd_drainer, name=("%s-stderr" % command),
                                    args=(self.sp.stderr, [self.stderr_file, self.stderr_tee],
                                          self.stderr_lock))
        self.stderr_thread.daemon = True

        self.stdout_thread.start()
        self.stderr_thread.start()

    @staticmethod
    def _stdin_string_drainer(input_string, stdin_pipe):
        """
        input is a string and output is PIPE
        """
        try:
            while True:
                # we can write PIPE_BUF bytes without blocking after a poll or
                # select we aren't doing either but let's write small chunks
                # anyway. POSIX requires PIPE_BUF is >= 512
                # 512 should be replaced with select.PIPE_BUF in Python 2.7+
                tmp = input_string[:512]
                if tmp == '':
                    break
                stdin_pipe.write(tmp)
                input_string = input_string[512:]
        finally:
            # close reading PIPE so that the reader doesn't block
            stdin_pipe.close()

    @staticmethod
    def _fd_drainer(input_pipe, outputs, lock):
        """
        input is a pipe and output is file-like. if lock is non-None, then
        we assume output isn't thread-safe
        """
        # if we don't have a lock object, then call a noop function like bool
        acquire = getattr(lock, 'acquire', bool)
        release = getattr(lock, 'release', bool)
        writable_objs = [obj for obj in outputs if hasattr(obj, 'write')]
        fileno = input_pipe.fileno()
        while True:
            # 1024 because that's what we did before
            tmp = os.read(fileno, 1024)
            if tmp == '':
                break
            acquire()
            try:
                for f in writable_objs:
                    f.write(tmp)
            finally:
                release()
        # don't close writeable_objs, the callee will close

    def output_prepare(self, stdout_file=None, stderr_file=None):
        raise NotImplementedError("This object automatically prepares its own "
                                  "output")

    def process_output(self, stdout=True, final_read=False):
        raise NotImplementedError("This object has background threads "
                                  "automatically polling the process. Use the "
                                  "locked accessors")

    def get_stdout(self):
        self.stdout_lock.acquire()
        tmp = self.stdout_file.getvalue()
        self.stdout_lock.release()
        return tmp

    def get_stderr(self):
        self.stderr_lock.acquire()
        tmp = self.stderr_file.getvalue()
        self.stderr_lock.release()
        return tmp

    def cleanup(self):
        raise NotImplementedError("This must be waited for to get a result")

    def _kill_self_process(self):
        try:
            os.kill(self.sp.pid, signal.SIGTERM)
        except OSError:
            pass  # don't care if the process is already gone

    def wait_for(self, timeout=None):
        """
        Wait for the process to finish. When timeout is provided, process is
        safely destroyed after timeout.
        :param timeout: Acceptable timeout
        :return: results of this command
        """
        if timeout is None:
            self.sp.wait()

        if timeout > 0:
            start_time = time.time()
            while time.time() - start_time < timeout:
                self.result.exit_status = self.sp.poll()
                if self.result.exit_status is not None:
                    break
        else:
            timeout = 1     # Increase the timeout to check if it really died
        # first need to kill the threads and process, then no more locking
        # issues for superclass's cleanup function
        self.kill_func()
        # Verify it was really killed with provided kill function
        stop_time = time.time() + timeout
        while time.time() < stop_time:
            self.result.exit_status = self.sp.poll()
            if self.result.exit_status is not None:
                break
        else:   # Process is immune against self.kill_func() use -9
            try:
                os.kill(self.sp.pid, signal.SIGKILL)
            except OSError:
                pass  # don't care if the process is already gone
        # we need to fill in parts of the result that aren't done automatically
        try:
            _, self.result.exit_status = os.waitpid(self.sp.pid, 0)
        except OSError:
            self.result.exit_status = self.sp.poll()
        self.result.duration = time.time() - self.start_time
        assert self.result.exit_status is not None

        # make sure we've got stdout and stderr
        self.stdout_thread.join(1)
        self.stderr_thread.join(1)
        assert not self.stdout_thread.isAlive()
        assert not self.stderr_thread.isAlive()

        super(AsyncJob, self).cleanup()

        return self.result


def ip_to_long(ip):
    # !L is a long in network byte order
    return struct.unpack('!L', socket.inet_aton(ip))[0]


def long_to_ip(number):
    # See above comment.
    return socket.inet_ntoa(struct.pack('!L', number))


def create_subnet_mask(bits):
    return (1 << 32) - (1 << 32 - bits)


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


def read_one_line(filename):
    return open(filename, 'r').readline().rstrip('\n')


def read_file(filename):
    f = open(filename)
    try:
        return f.read()
    finally:
        f.close()


def get_field(data, param, linestart="", sep=" "):
    """
    Parse data from string.
    :param data: Data to parse.
        example:
          data:
             cpu   324 345 34  5 345
             cpu0  34  11  34 34  33
             ^^^^
             start of line
             params 0   1   2  3   4
    :param param: Position of parameter after linestart marker.
    :param linestart: String to which start line with parameters.
    :param sep: Separator between parameters regular expression.
    """
    search = re.compile(r"(?<=^%s)\s*(.*)" % linestart, re.MULTILINE)
    find = search.search(data)
    if find is not None:
        return re.split("%s" % sep, find.group(1))[param]
    else:
        print "There is no line which starts with %s in data." % linestart
        return None


def write_one_line(filename, line):
    open_write_close(filename, line.rstrip('\n') + '\n')


def open_write_close(filename, data):
    f = open(filename, 'w')
    try:
        f.write(data)
    finally:
        f.close()


def matrix_to_string(matrix, header=None):
    """
    Return a pretty, aligned string representation of a nxm matrix.

    This representation can be used to print any tabular data, such as
    database results. It works by scanning the lengths of each element
    in each column, and determining the format string dynamically.

    :param matrix: Matrix representation (list with n rows of m elements).
    :param header: Optional tuple or list with header elements to be displayed.
    """
    if type(header) is list:
        header = tuple(header)
    lengths = []
    if header:
        for column in header:
            lengths.append(len(column))
    for row in matrix:
        for i, column in enumerate(row):
            column = unicode(column).encode("utf-8")
            cl = len(column)
            try:
                ml = lengths[i]
                if cl > ml:
                    lengths[i] = cl
            except IndexError:
                lengths.append(cl)

    lengths = tuple(lengths)
    format_string = ""
    for length in lengths:
        format_string += "%-" + str(length) + "s "
    format_string += "\n"

    matrix_str = ""
    if header:
        matrix_str += format_string % header
    for row in matrix:
        matrix_str += format_string % tuple(row)

    return matrix_str


class Statistic(object):

    """
    Class to display and collect average,
    max and min values of a given data set.
    """

    def __init__(self):
        self._sum = 0
        self._count = 0
        self._max = None
        self._min = None

    def get_average(self):
        if self._count != 0:
            return self._sum / self._count
        else:
            return None

    def get_min(self):
        return self._min

    def get_max(self):
        return self._max

    def record(self, value):
        """
        Record new value to statistic.
        """
        self._count += 1
        self._sum += value
        if not self._max or self._max < value:
            self._max = value
        if not self._min or self._min > value:
            self._min = value


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


def write_keyval(path, dictionary, type_tag=None, tap_report=None):
    """
    Write a key-value pair format file out to a file. This uses append
    mode to open the file, so existing text will not be overwritten or
    reparsed.

    If type_tag is None, then the key must be composed of alphanumeric
    characters (or dashes+underscores). However, if type-tag is not
    null then the keys must also have "{type_tag}" as a suffix. At
    the moment the only valid values of type_tag are "attr" and "perf".

    :param path: full path of the file to be written
    :param dictionary: the items to write
    :param type_tag: see text above
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

    # same for tap
    if tap_report is not None and tap_report.do_tap_report:
        tap_report.record_keyval(path, dictionary, type_tag=type_tag)


class FileFieldMonitor(object):

    """
    Monitors the information from the file and reports it's values.

    It gather the information at start and stop of the measurement or
    continuously during the measurement.
    """
    class Monitor(Thread):

        """
        Internal monitor class to ensure continuous monitor of monitored file.
        """

        def __init__(self, master):
            """
            :param master: Master class which control Monitor
            """
            Thread.__init__(self)
            self.master = master

        def run(self):
            """
            Start monitor in thread mode
            """
            while not self.master.end_event.isSet():
                self.master._get_value(self.master.logging)
                time.sleep(self.master.time_step)

    def __init__(self, status_file, data_to_read, mode_diff, continuously=False,
                 contlogging=False, separator=" +", time_step=0.1):
        """
        Initialize variables.
        :param status_file: File contain status.
        :param mode_diff: If True make a difference of value, else average.
        :param data_to_read: List of tuples with data position.
            format: [(start_of_line,position in params)]
            example:
              data:
                 cpu   324 345 34  5 345
                 cpu0  34  11  34 34  33
                 ^^^^
                 start of line
                 params 0   1   2  3   4
        :param mode_diff: True to subtract old value from new value,
            False make average of the values.
        :param continuously: Start the monitoring thread using the time_step
            as the measurement period.
        :param contlogging: Log data in continuous run.
        :param separator: Regular expression of separator.
        :param time_step: Time period of the monitoring value.
        """
        self.end_event = Event()
        self.start_time = 0
        self.end_time = 0
        self.test_time = 0

        self.status_file = status_file
        self.separator = separator
        self.data_to_read = data_to_read
        self.num_of_params = len(self.data_to_read)
        self.mode_diff = mode_diff
        self.continuously = continuously
        self.time_step = time_step

        self.value = [0 for i in range(self.num_of_params)]
        self.old_value = [0 for i in range(self.num_of_params)]
        self.log = []
        self.logging = contlogging

        self.started = False
        self.num_of_get_value = 0
        self.monitor = None

    def _get_value(self, logging=True):
        """
        Return current values.
        :param logging: If true log value in memory. There can be problem
          with long run.
        """
        data = read_file(self.status_file)
        value = []
        for i in range(self.num_of_params):
            value.append(int(get_field(data,
                                       self.data_to_read[i][1],
                                       self.data_to_read[i][0],
                                       self.separator)))

        if logging:
            self.log.append(value)
        if not self.mode_diff:
            value = map(lambda x, y: x + y, value, self.old_value)

        self.old_value = value
        self.num_of_get_value += 1
        return value

    def start(self):
        """
        Start value monitor.
        """
        if self.started:
            self.stop()
        self.old_value = [0 for i in range(self.num_of_params)]
        self.num_of_get_value = 0
        self.log = []
        self.end_event.clear()
        self.start_time = time.time()
        self._get_value()
        self.started = True
        if (self.continuously):
            self.monitor = FileFieldMonitor.Monitor(self)
            self.monitor.start()

    def stop(self):
        """
        Stop value monitor.
        """
        if self.started:
            self.started = False
            self.end_time = time.time()
            self.test_time = self.end_time - self.start_time
            self.value = self._get_value()
            if (self.continuously):
                self.end_event.set()
                self.monitor.join()
            if (self.mode_diff):
                self.value = map(lambda x, y: x - y, self.log[-1], self.log[0])
            else:
                self.value = map(lambda x: x / self.num_of_get_value,
                                 self.value)

    def get_status(self):
        """
        :return: Status of monitored process average value,
            time of test and array of monitored values and time step of
            continuous run.
        """
        if self.started:
            self.stop()
        if self.mode_diff:
            for i in range(len(self.log) - 1):
                self.log[i] = (map(lambda x, y: x - y,
                                   self.log[i + 1], self.log[i]))
            if self.log:
                self.log.pop()
        return (self.value, self.test_time, self.log, self.time_step)


def is_url(path):
    """Return true if path looks like a URL"""
    # for now, just handle http and ftp
    url_parts = urlparse.urlparse(path)
    return (url_parts[0] in ('http', 'ftp', 'git'))  # pylint: disable=E1136


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


def hash(type, input=None):
    """
    Returns an hash object of type md5 or sha1. This function is implemented in
    order to encapsulate hash objects in a way that is compatible with python
    2.4 and python 2.6 without warnings.

    Note that even though python 2.6 hashlib supports hash types other than
    md5 and sha1, we are artificially limiting the input values in order to
    make the function to behave exactly the same among both python
    implementations.

    :param input: Optional input string that will be used to update the hash.
    """
    if type not in ['md5', 'sha1']:
        raise ValueError("Unsupported hash type: %s" % type)

    try:
        hash = hashlib.new(type)
    except NameError:
        if type == 'md5':
            hash = md5.new()
        elif type == 'sha1':
            hash = sha.new()

    if input:
        hash.update(input)

    return hash


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
        # ParseResult is subscriptable, ignore E1136
        filename = os.path.basename(url_parts[2])  # pylint: disable=E1136
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
        module_name = os.path.basename(os.path.dirname(srcdir))
        module_parent = os.path.dirname(srcdir)
        base_autotest = os.path.abspath(os.path.join(module_parent, "..", ".."))
        tmp_autotest = os.path.join(base_autotest, 'tmp')
        tests_dir = os.path.join(base_autotest, 'tests')
        site_tests_dir = os.path.join(base_autotest, 'site_tests')
        tmp_site_tests_dir = os.path.join(tmp_autotest, 'site_tests')
        profilers_dir = os.path.join(base_autotest, 'profilers')
        other_tests_dir = settings.get_value("COMMON", "test_dir", default="")
        source_code_dir = ""
        for d in [other_tests_dir,
                  tmp_site_tests_dir,
                  site_tests_dir,
                  tests_dir,
                  profilers_dir]:
            source_code_dir = os.path.join(d, module_name, "src")
            if os.path.isdir(source_code_dir):
                break

        if not os.path.isdir(srcdir):
            tdir = os.path.dirname(srcdir)
            if not os.path.isdir(tdir):
                os.makedirs(tdir)
            if os.path.isdir(source_code_dir):
                shutil.copytree(source_code_dir, srcdir)
            else:
                os.mkdir(srcdir)

        patch_file_list = glob.glob(os.path.join(
                                    (os.path.dirname(source_code_dir)), "*.patch"))
        for patch_src in patch_file_list:
            patch_dst = os.path.join(os.path.dirname(srcdir),
                                     os.path.basename(patch_src))
            shutil.copyfile(patch_src, patch_dst)

        install(*args, **dargs)
        pickle.dump(new_version, open(versionfile, 'w'))


def get_stderr_level(stderr_is_expected):
    if stderr_is_expected:
        return DEFAULT_STDOUT_LEVEL
    return DEFAULT_STDERR_LEVEL


def run(command, timeout=None, ignore_status=False,
        stdout_tee=None, stderr_tee=None, verbose=True, stdin=None,
        stderr_is_expected=None, args=()):
    """
    Run a command on the host.

    :param command: the command line string.
    :param timeout: time limit in seconds before attempting to kill the
            running process. The run() function will take a few seconds
            longer than 'timeout' to complete if it has to kill the process.
    :param ignore_status: do not raise an exception, no matter what the exit
            code of the command is.
    :param stdout_tee: optional file-like object to which stdout data
            will be written as it is generated (data will still be stored
            in result.stdout).
    :param stderr_tee: likewise for stderr.
    :param verbose: if True, log the command being run.
    :param stdin: stdin to pass to the executed process (can be a file
            descriptor, a file object of a real file or a string).
    :param args: sequence of strings of arguments to be given to the command
            inside " quotes after they have been escaped for that; each
            element in the sequence will be given as a separate command
            argument

    :return: a CmdResult object

    :raise CmdError: the exit code of the command execution was not 0
    """
    if isinstance(args, basestring):
        raise TypeError('Got a string for the "args" keyword argument, '
                        'need a sequence.')

    for arg in args:
        command += ' "%s"' % sh_escape(arg)
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
    """
    Behaves the same as run() with the following exceptions:

    - commands is a list of commands to run in parallel.
    - ignore_status toggles whether or not an exception should be raised
      on any error.

    :return: a list of CmdResult objects
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


class InterruptedThread(Thread):

    """
    Run a function in a background thread.
    """

    def __init__(self, target, args=(), kwargs={}):
        """
        Initialize the instance.

        :param target: Function to run in the thread.
        :param args: Arguments to pass to target.
        :param kwargs: Keyword arguments to pass to target.
        """
        Thread.__init__(self)
        self._target = target
        self._args = args
        self._kwargs = kwargs

    def run(self):
        """
        Run target (passed to the constructor).  No point in calling this
        function directly.  Call start() to make this function run in a new
        thread.
        """
        self._e = None
        self._retval = None
        try:
            try:
                self._retval = self._target(*self._args, **self._kwargs)
            except Exception:
                self._e = sys.exc_info()
                raise
        finally:
            # Avoid circular references (start() may be called only once so
            # it's OK to delete these)
            del self._target, self._args, self._kwargs

    def join(self, timeout=None, suppress_exception=False):
        """
        Join the thread.  If target raised an exception, re-raise it.
        Otherwise, return the value returned by target.

        :param timeout: Timeout value to pass to threading.Thread.join().
        :param suppress_exception: If True, don't re-raise the exception.
        """
        Thread.join(self, timeout)
        try:
            if self._e:
                if not suppress_exception:
                    # Because the exception was raised in another thread, we
                    # need to explicitly insert the current context into it
                    s = error.exception_context(self._e[1])
                    s = error.join_contexts(error.get_context(), s)
                    error.set_exception_context(self._e[1], s)
                    raise self._e[0], self._e[1], self._e[2]
            else:
                return self._retval
        finally:
            # Avoid circular references (join() may be called multiple times
            # so we can't delete these)
            self._e = None
            self._retval = None


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
            bg_job.process_output(stdout=True, final_read=True)
            bg_job.process_output(stdout=False, final_read=True)
    finally:
        # close our ends of the pipes to the sp no matter what
        for bg_job in bg_jobs:
            bg_job.cleanup()

    if timeout_error:
        # TODO: This needs to be fixed to better represent what happens when
        # running in parallel. However this is backwards compatible, so it will
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

    read_list = []
    write_list = []
    reverse_dict = {}

    for bg_job in bg_jobs:
        read_list.append(bg_job.sp.stdout)
        read_list.append(bg_job.sp.stderr)
        reverse_dict[bg_job.sp.stdout] = (bg_job, True)
        reverse_dict[bg_job.sp.stderr] = (bg_job, False)
        if bg_job.string_stdin is not None:
            write_list.append(bg_job.sp.stdin)
            reverse_dict[bg_job.sp.stdin] = bg_job

    if timeout:
        stop_time = start_time + timeout
        time_left = stop_time - time.time()
    else:
        time_left = None  # so that select never times out

    while not timeout or time_left > 0:
        # select will return when we may write to stdin or when there is
        # stdout/stderr output we can read (including when it is
        # EOF, that is the process has terminated).
        read_ready, write_ready, _ = select.select(read_list, write_list, [],
                                                   SELECT_TIMEOUT)

        # os.read() has to be used instead of
        # subproc.stdout.read() which will otherwise block
        for file_obj in read_ready:
            bg_job, is_stdout = reverse_dict[file_obj]
            bg_job.process_output(is_stdout)

        for file_obj in write_ready:
            # we can write PIPE_BUF bytes without blocking
            # POSIX requires PIPE_BUF is >= 512
            bg_job = reverse_dict[file_obj]
            file_obj.write(bg_job.string_stdin[:512])
            bg_job.string_stdin = bg_job.string_stdin[512:]
            # no more input data, close stdin, remove it from the select set
            if not bg_job.string_stdin:
                file_obj.close()
                write_list.remove(file_obj)
                del reverse_dict[file_obj]

        all_jobs_finished = True
        for bg_job in bg_jobs:
            if bg_job.result.exit_status is not None:
                continue

            bg_job.result.exit_status = bg_job.sp.poll()
            if bg_job.result.exit_status is not None:
                # process exited, remove its stdout/stdin from the select set
                bg_job.result.duration = time.time() - start_time
                read_list.remove(bg_job.sp.stdout)
                read_list.remove(bg_job.sp.stderr)
                del reverse_dict[bg_job.sp.stdout]
                del reverse_dict[bg_job.sp.stderr]
            else:
                all_jobs_finished = False

        if all_jobs_finished:
            return False

        if timeout:
            time_left = stop_time - time.time()

    # Kill all processes which did not complete prior to timeout
    for bg_job in bg_jobs:
        if bg_job.result.exit_status is not None:
            continue

        logging.warn('run process timeout (%s) fired on: %s', timeout,
                     bg_job.command)
        nuke_subprocess(bg_job.sp)
        bg_job.result.exit_status = bg_job.sp.poll()
        bg_job.result.duration = time.time() - start_time

    return True


def get_children_pids(ppid):
    """
    Get all PIDs of children/threads of parent ppid
    param ppid: parent PID
    return: list of PIDs of all children/threads of ppid
    """
    return (system_output("ps -L --ppid=%d -o lwp" % ppid).split('\n')[1:])


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


def nuke_pid(pid, signal_queue=(signal.SIGTERM, signal.SIGKILL)):
    # the process has not terminated within timeout,
    # kill it via an escalating series of signals.
    for sig in signal_queue:
        if signal_pid(pid, sig):
            return

    # no signal successfully terminated the process
    raise error.AutoservRunError('Could not kill %d' % pid, None)


def system(command, timeout=None, ignore_status=False, verbose=True):
    """
    Run a command

    :param timeout: timeout in seconds
    :param ignore_status: if ignore_status=False, throw an exception if the
            command's exit code is non-zero
            if ignore_status=True, return the exit code.
    :param verbose: if True, log the command being run.

    :return: exit status of command
            (note, this will always be zero unless ignore_status=True)
    """
    return run(command, timeout=timeout, ignore_status=ignore_status,
               stdout_tee=TEE_TO_LOGS, stderr_tee=TEE_TO_LOGS,
               verbose=verbose).exit_status


def system_parallel(commands, timeout=None, ignore_status=False):
    """This function returns a list of exit statuses for the respective
    list of commands."""
    return [bg_jobs.exit_status for bg_jobs in
            run_parallel(commands, timeout=timeout, ignore_status=ignore_status,
                         stdout_tee=TEE_TO_LOGS, stderr_tee=TEE_TO_LOGS)]


def system_output(command, timeout=None, ignore_status=False,
                  retain_output=False, args=(), verbose=True):
    """
    Run a command and return the stdout output.

    :param command: command string to execute.
    :param timeout: time limit in seconds before attempting to kill the
            running process. The function will take a few seconds longer
            than 'timeout' to complete if it has to kill the process.
    :param ignore_status: do not raise an exception, no matter what the exit
            code of the command is.
    :param retain_output: set to True to make stdout/stderr of the command
            output to be also sent to the logging system
    :param args: sequence of strings of arguments to be given to the command
            inside " quotes after they have been escaped for that; each
            element in the sequence will be given as a separate command
            argument
    :param verbose: if True, log the command being run.

    :return: a string with the stdout output of the command.
    """
    if retain_output:
        out = run(command, timeout=timeout, ignore_status=ignore_status,
                  stdout_tee=TEE_TO_LOGS, stderr_tee=TEE_TO_LOGS,
                  verbose=verbose, args=args).stdout
    else:
        out = run(command, timeout=timeout, ignore_status=ignore_status,
                  verbose=verbose, args=args).stdout
    if out[-1:] == '\n':
        out = out[:-1]
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
        if out[-1:] == '\n':
            out = out[:-1]
    return out


class ForAll(list):

    def __getattr__(self, name):
        def wrapper(*args, **kargs):
            return map(lambda o: o.__getattribute__(name)(*args, **kargs), self)
        return wrapper


class ForAllP(list):

    """
    Parallel version of ForAll
    """

    def __getattr__(self, name):
        def wrapper(*args, **kargs):
            threads = []
            for o in self:
                threads.append(InterruptedThread(o.__getattribute__(name),
                                                 args=args, kwargs=kargs))
            for t in threads:
                t.start()
            return map(lambda t: t.join(), threads)
        return wrapper


class ForAllPSE(list):

    """
    Parallel version of and suppress exception.
    """

    def __getattr__(self, name):
        def wrapper(*args, **kargs):
            threads = []
            for o in self:
                threads.append(InterruptedThread(o.__getattribute__(name),
                                                 args=args, kwargs=kargs))
            for t in threads:
                t.start()

            result = []
            for t in threads:
                ret = {}
                try:
                    ret["return"] = t.join()
                except Exception:
                    ret["exception"] = sys.exc_info()
                    ret["args"] = args
                    ret["kargs"] = kargs
                result.append(ret)
            return result
        return wrapper


def etraceback(prep, exc_info):
    """
    Enhanced Traceback formats traceback into lines "prep: line\nname: line"
    :param prep: desired line preposition
    :param exc_info: sys.exc_info of the exception
    :return: string which contains beautifully formatted exception
    """
    out = ""
    for line in traceback.format_exception(exc_info[0], exc_info[1],
                                           exc_info[2]):
        out += "%s: %s" % (prep, line)
    return out


def log_last_traceback(msg=None, log=logging.error):
    """
    Writes last traceback into specified log.
    :param msg: Override the default message. ["Original traceback"]
    :param log: Where to log the traceback [logging.error]
    """
    if not log:
        log = logging.error
    if msg:
        log(msg)
    exc_type, exc_value, exc_traceback = sys.exc_info()
    if not exc_traceback:
        log('Requested log_last_traceback but no exception was raised.')
        return
    log("Original " +
        "".join(traceback.format_exception(exc_type, exc_value,
                                           exc_traceback)))


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


class SystemLoad(object):

    """
    Get system and/or process values and return average value of load.
    """

    def __init__(self, pids, advanced=False, time_step=0.1, cpu_cont=False,
                 use_log=False):
        """
        :param pids: List of pids to be monitored. If pid = 0 whole system will
          be monitored. pid == 0 means whole system.
        :param advanced: monitor add value for system irq count and softirq
          for process minor and maior page fault
        :param time_step: Time step for continuous monitoring.
        :param cpu_cont: If True monitor CPU load continuously.
        :param use_log: If true every monitoring is logged for dump.
        """
        self.pids = []
        self.stats = {}
        for pid in pids:
            if pid == 0:
                cpu = FileFieldMonitor("/proc/stat",
                                       [("cpu", 0),  # User Time
                                        ("cpu", 2),  # System Time
                                        ("intr", 0),  # IRQ Count
                                        ("softirq", 0)],  # Soft IRQ Count
                                       True,
                                       cpu_cont,
                                       use_log,
                                       " +",
                                       time_step)
                mem = FileFieldMonitor("/proc/meminfo",
                                       [("MemTotal:", 0),  # Mem Total
                                        ("MemFree:", 0),  # Mem Free
                                        ("Buffers:", 0),  # Buffers
                                        ("Cached:", 0)],  # Cached
                                       False,
                                       True,
                                       use_log,
                                       " +",
                                       time_step)
                self.stats[pid] = ["TOTAL", cpu, mem]
                self.pids.append(pid)
            else:
                name = ""
                if (type(pid) is int):
                    self.pids.append(pid)
                    name = get_process_name(pid)
                else:
                    self.pids.append(pid[0])
                    name = pid[1]

                cpu = FileFieldMonitor("/proc/%d/stat" %
                                       self.pids[-1],
                                       [("", 13),  # User Time
                                        ("", 14),  # System Time
                                        ("", 9),  # Minority Page Fault
                                        ("", 11)],  # Majority Page Fault
                                       True,
                                       cpu_cont,
                                       use_log,
                                       " +",
                                       time_step)
                mem = FileFieldMonitor("/proc/%d/status" %
                                       self.pids[-1],
                                       [("VmSize:", 0),  # Virtual Memory Size
                                        ("VmRSS:", 0),  # Resident Set Size
                                        ("VmPeak:", 0),  # Peak VM Size
                                        ("VmSwap:", 0)],  # VM in Swap
                                       False,
                                       True,
                                       use_log,
                                       " +",
                                       time_step)
                self.stats[self.pids[-1]] = [name, cpu, mem]

        self.advanced = advanced

    def __str__(self):
        """
        Define format how to print
        """
        out = ""
        for pid in self.pids:
            for stat in self.stats[pid][1:]:
                out += str(stat.get_status()) + "\n"
        return out

    def start(self, pids=[]):
        """
        Start monitoring of the process system usage.
        :param pids: List of PIDs you intend to control. Use pids=[] to control
            all defined PIDs.
        """
        if pids == []:
            pids = self.pids

        for pid in pids:
            for stat in self.stats[pid][1:]:
                stat.start()

    def stop(self, pids=[]):
        """
        Stop monitoring of the process system usage.
        :param pids: List of PIDs you intend to control. Use pids=[] to control
            all defined PIDs.
        """
        if pids == []:
            pids = self.pids

        for pid in pids:
            for stat in self.stats[pid][1:]:
                stat.stop()

    def dump(self, pids=[]):
        """
        Get the status of monitoring.
        :param pids: List of PIDs you intend to control. Use pids=[] to control
            all defined PIDs.
         :return:
            tuple([cpu load], [memory load]):
                ([(PID1, (PID1_cpu_meas)), (PID2, (PID2_cpu_meas)), ...],
                 [(PID1, (PID1_mem_meas)), (PID2, (PID2_mem_meas)), ...])

            PID1_cpu_meas:
                average_values[], test_time, cont_meas_values[[]], time_step
            PID1_mem_meas:
                average_values[], test_time, cont_meas_values[[]], time_step
            where average_values[] are the measured values (mem_free,swap,...)
            which are described in SystemLoad.__init__()-FileFieldMonitor.
            cont_meas_values[[]] is a list of average_values in the sampling
            times.
        """
        if pids == []:
            pids = self.pids

        cpus = []
        memory = []
        for pid in pids:
            stat = (pid, self.stats[pid][1].get_status())
            cpus.append(stat)
        for pid in pids:
            stat = (pid, self.stats[pid][2].get_status())
            memory.append(stat)

        return (cpus, memory)

    def get_cpu_status_string(self, pids=[]):
        """
        Convert status to string array.
        :param pids: List of PIDs you intend to control. Use pids=[] to control
            all defined PIDs.
        :return: String format to table.
        """
        if pids == []:
            pids = self.pids

        headers = ["NAME",
                   ("%7s") % "PID",
                   ("%5s") % "USER",
                   ("%5s") % "SYS",
                   ("%5s") % "SUM"]
        if self.advanced:
            headers.extend(["MINFLT/IRQC",
                            "MAJFLT/SOFTIRQ"])
        headers.append(("%11s") % "TIME")
        textstatus = []
        for pid in pids:
            stat = self.stats[pid][1].get_status()
            time = stat[1]
            stat = stat[0]
            textstatus.append(["%s" % self.stats[pid][0],
                               "%7s" % pid,
                               "%4.0f%%" % (stat[0] / time),
                               "%4.0f%%" % (stat[1] / time),
                               "%4.0f%%" % ((stat[0] + stat[1]) / time),
                               "%10.3fs" % time])
            if self.advanced:
                textstatus[-1].insert(-1, "%11d" % stat[2])
                textstatus[-1].insert(-1, "%14d" % stat[3])

        return matrix_to_string(textstatus, tuple(headers))

    def get_mem_status_string(self, pids=[]):
        """
        Convert status to string array.
        :param pids: List of PIDs you intend to control. Use pids=[] to control
            all defined PIDs.
        :return: String format to table.
        """
        if pids == []:
            pids = self.pids

        headers = ["NAME",
                   ("%7s") % "PID",
                   ("%8s") % "TOTAL/VMSIZE",
                   ("%8s") % "FREE/VMRSS",
                   ("%8s") % "BUFFERS/VMPEAK",
                   ("%8s") % "CACHED/VMSWAP",
                   ("%11s") % "TIME"]
        textstatus = []
        for pid in pids:
            stat = self.stats[pid][2].get_status()
            time = stat[1]
            stat = stat[0]
            textstatus.append(["%s" % self.stats[pid][0],
                               "%7s" % pid,
                               "%10dMB" % (stat[0] / 1024),
                               "%8dMB" % (stat[1] / 1024),
                               "%12dMB" % (stat[2] / 1024),
                               "%11dMB" % (stat[3] / 1024),
                               "%10.3fs" % time])

        return matrix_to_string(textstatus, tuple(headers))


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
        return  # exists only in dest
    elif not os.path.exists(dest):
        if os.path.isfile(src):
            shutil.copy2(src, dest)  # file only in src
        else:
            shutil.copytree(src, dest, symlinks=True)  # dir only in src
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
        wrapper = textwrap.TextWrapper(width=78,
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
            test_index = random.randint(0, len(self.test_list) - 1)
            if self.run_sequentially:
                test_index = 0
            (args, dargs) = self.test_list.pop(test_index)
            fn(*args, **dargs)


def import_site_module(path, module, dummy=None, modulefile=None):
    """
    Try to import the site specific module if it exists.

    :param path full filename of the source file calling this (ie __file__)
    :param module full module name
    :param dummy dummy value to return in case there is no symbol to import
    :param modulefile module filename

    :return: site specific module or dummy

    :raise ImportError if the site file exists but imports fails
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

    :param path full filename of the source file calling this (ie __file__)
    :param module full module name
    :param name symbol name to be imported from the site file
    :param dummy dummy value to return in case there is no symbol to import
    :param modulefile module filename

    :return: site specific symbol or dummy

    :raise ImportError if the site file exists but imports fails
    """
    module = import_site_module(path, module, modulefile=modulefile)
    if not module:
        return dummy

    # special unique value to tell us if the symbol can't be imported
    cant_import = object()

    obj = getattr(module, name, cant_import)
    if obj is cant_import:
        logging.debug("unable to import site symbol '%s', using non-site "
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


def get_pid_path(program_name, pid_files_dir=None):
    if pid_files_dir is None:
        pid_files_dir = settings.get_value("SERVER", 'pid_files_dir',
                                           default="")

    if not pid_files_dir:
        base_dir = os.path.dirname(__file__)
        pid_path = os.path.abspath(os.path.join(base_dir, "..", "..",
                                                "%s.pid" % program_name))
    else:
        pid_path = os.path.join(pid_files_dir, "%s.pid" % program_name)

    return pid_path


def write_pid(program_name, pid_files_dir=None):
    """
    Try to drop <program_name>.pid in the main autotest directory.

    Args:
      program_name: prefix for file name
    """
    pidfile = open(get_pid_path(program_name, pid_files_dir), "w")
    try:
        pidfile.write("%s\n" % os.getpid())
    finally:
        pidfile.close()


def delete_pid_file_if_exists(program_name, pid_files_dir=None):
    """
    Tries to remove <program_name>.pid from the main autotest directory.
    """
    pidfile_path = get_pid_path(program_name, pid_files_dir)

    try:
        os.remove(pidfile_path)
    except OSError:
        if not os.path.exists(pidfile_path):
            return
        raise


def get_pid_from_file(program_name, pid_files_dir=None):
    """
    Reads the pid from <program_name>.pid in the autotest directory.

    :param program_name the name of the program
    :return: the pid if the file exists, None otherwise.
    """
    pidfile_path = get_pid_path(program_name, pid_files_dir)
    if not os.path.exists(pidfile_path):
        return None

    pidfile = open(get_pid_path(program_name, pid_files_dir), 'r')

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


def get_process_name(pid):
    """
    Get process name from PID.
    :param pid: PID of process.
    """
    return get_field(read_file("/proc/%d/stat" % pid), 1)[1:-1]


def program_is_alive(program_name, pid_files_dir=None):
    """
    Checks if the process is alive and not in Zombie state.

    :param program_name the name of the program
    :return: True if still alive, False otherwise
    """
    pid = get_pid_from_file(program_name, pid_files_dir)
    if pid is None:
        return False
    return pid_is_alive(pid)


def signal_program(program_name, sig=signal.SIGTERM, pid_files_dir=None):
    """
    Sends a signal to the process listed in <program_name>.pid

    :param program_name the name of the program
    :param sig signal to send
    """
    pid = get_pid_from_file(program_name, pid_files_dir)
    if pid:
        signal_pid(pid, sig)


def get_relative_path(path, reference):
    """Given 2 absolute paths "path" and "reference", compute the path of
    "path" as relative to the directory "reference".

    :param path the absolute path to convert to a relative path
    :param reference an absolute directory path to which the relative
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


def configure(extra=None, configure='./configure'):
    """
    Run configure passing in the correct host, build, and target options.

    :param extra: extra command line arguments to pass to configure
    :param configure: which configure script to use
    """
    args = []
    if 'CHOST' in os.environ:
        args.append('--host=' + os.environ['CHOST'])
    if 'CBUILD' in os.environ:
        args.append('--build=' + os.environ['CBUILD'])
    if 'CTARGET' in os.environ:
        args.append('--target=' + os.environ['CTARGET'])
    if extra:
        args.append(extra)

    system('%s %s' % (configure, ' '.join(args)))


def make(extra='', make='make', timeout=None, ignore_status=False):
    """
    Run make, adding MAKEOPTS to the list of options.

    :param extra: extra command line arguments to pass to make.
    """
    cmd = '%s %s %s' % (make, os.environ.get('MAKEOPTS', ''), extra)
    return system(cmd, timeout=timeout, ignore_status=ignore_status)


def compare_versions(ver1, ver2):
    """Version number comparison between ver1 and ver2 strings.

    >>> compare_tuple("1", "2")
    -1
    >>> compare_tuple("foo-1.1", "foo-1.2")
    -1
    >>> compare_tuple("1.2", "1.2a")
    -1
    >>> compare_tuple("1.2b", "1.2a")
    1
    >>> compare_tuple("1.3.5.3a", "1.3.5.3b")
    -1

    Args:
        ver1: version string
        ver2: version string

    Returns:
        int:  1 if ver1 >  ver2
              0 if ver1 == ver2
             -1 if ver1 <  ver2
    """
    ax = re.split('[.-]', ver1)
    ay = re.split('[.-]', ver2)
    while len(ax) > 0 and len(ay) > 0:
        cx = ax.pop(0)
        cy = ay.pop(0)
        maxlen = max(len(cx), len(cy))
        c = cmp(cx.zfill(maxlen), cy.zfill(maxlen))
        if c != 0:
            return c
    return cmp(len(ax), len(ay))


def args_to_dict(args):
    """Convert autoserv extra arguments in the form of key=val or key:val to a
    dictionary.  Each argument key is converted to lowercase dictionary key.

    Args:
        args - list of autoserv extra arguments.

    Returns:
        dictionary
    """
    arg_re = re.compile(r'(\w+)[:=](.*)$')
    dict = {}
    for arg in args:
        match = arg_re.match(arg)
        if match:
            dict[match.group(1).lower()] = match.group(2)
        else:
            logging.warning("args_to_dict: argument '%s' doesn't match "
                            "'%s' pattern. Ignored." % (arg, arg_re.pattern))
    return dict


def get_unused_port():
    """
    Finds a semi-random available port. A race condition is still
    possible after the port number is returned, if another process
    happens to bind it.

    Returns:
        A port number that is unused on both TCP and UDP.
    """

    def try_bind(port, socket_type, socket_proto):
        s = socket.socket(socket.AF_INET, socket_type, socket_proto)
        try:
            try:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(('', port))
                return s.getsockname()[1]
            except socket.error:
                return None
        finally:
            s.close()

    # On the 2.6 kernel, calling try_bind() on UDP socket returns the
    # same port over and over. So always try TCP first.
    while True:
        # Ask the OS for an unused port.
        port = try_bind(0, socket.SOCK_STREAM, socket.IPPROTO_TCP)
        # Check if this port is unused on the other protocol.
        if port and try_bind(port, socket.SOCK_DGRAM, socket.IPPROTO_UDP):
            return port


def ask(question, auto=False):
    """
    Raw input with a prompt that emulates logging.

    :param question: Question to be asked
    :param auto: Whether to return "y" instead of asking the question
    """
    if auto:
        logging.info("%s (y/n) y" % question)
        return "y"
    return raw_input("%s INFO | %s (y/n) " %
                     (time.strftime("%H:%M:%S", time.localtime()), question))


def display_data_size(size):
    '''
    Display data size in human readable units.

    :type size: int
    :param size: Data size, in Bytes.
    :return: Human readable string with data size.
    '''
    prefixes = ['B', 'kB', 'MB', 'GB', 'TB']
    i = 0
    while size > 1000.0:
        size /= 1000.0
        i += 1
    return '%.2f %s' % (size, prefixes[i])


def cpu_affinity_by_task(pid, vcpu_pid):
    """
    This function returns the allowed cpus from the proc entry
    for each vcpu's through its task id for a pid(of a VM)
    """

    cmd = "cat /proc/%s/task/%s/status|grep Cpus_allowed:| awk '{print $2}'" % (pid, vcpu_pid)
    output = system_output(cmd, ignore_status=False)
    return output


def convert_data_size(size, default_sufix='B'):
    '''
    Convert data size from human readable units to an int of arbitrary size.

    :param size: Human readable data size representation (string).
    :param default_sufix: Default sufix used to represent data.
    :return: Int with data size in the appropriate order of magnitude.
    '''
    orders = {'B': 1,
              'K': 1024,
              'M': 1024 * 1024,
              'G': 1024 * 1024 * 1024,
              'T': 1024 * 1024 * 1024 * 1024,
              }

    order = re.findall("([BbKkMmGgTt])", size[-1])
    if not order:
        size += default_sufix
        order = [default_sufix]

    return int(float(size[0:-1]) * orders[order[0].upper()])


def interactive_download(url, output_file, title='', chunk_size=100 * 1024):
    '''
    Interactively downloads a given file url to a given output file

    :type url: string
    :param url: URL for the file to be download
    :type output_file: string
    :param output_file: file name or absolute path on which to save the file to
    :type title: string
    :param title: optional title to go along the progress bar
    :type chunk_size: integer
    :param chunk_size: amount of data to read at a time
    '''
    output_dir = os.path.dirname(output_file)
    output_file = open(output_file, 'w+b')
    input_file = urllib2.urlopen(url)

    try:
        file_size = int(input_file.headers['Content-Length'])
    except KeyError:
        raise ValueError('Could not find file size in HTTP headers')

    logging.info('Downloading %s, %s to %s', os.path.basename(url),
                 display_data_size(file_size), output_dir)

    # Calculate progress bar size based on title size
    if title:
        width = progressbar.ProgressBar.DEFAULT_WIDTH - len(title)
        progress_bar = progressbar.ProgressBar(maximum=file_size,
                                               width=width, title=title)
    else:
        progress_bar = progressbar.ProgressBar(maximum=file_size)

    # Download the file, while interactively updating the progress
    progress_bar.update_screen()
    while True:
        data = input_file.read(chunk_size)
        if data:
            progress_bar.increment(len(data))
            output_file.write(data)
        else:
            progress_bar.update(file_size)
            print
            break

    output_file.close()


def generate_random_string(length, ignore_str=string.punctuation,
                           convert_str=""):
    """
    Return a random string using alphanumeric characters.

    :param length: Length of the string that will be generated.
    :param ignore_str: Characters that will not include in generated string.
    :param convert_str: Characters that need to be escaped (prepend "\\").

    :return: The generated random string.
    """
    r = random.SystemRandom()
    str = ""
    chars = string.letters + string.digits + string.punctuation
    if not ignore_str:
        ignore_str = ""
    for i in ignore_str:
        chars = chars.replace(i, "")

    while length > 0:
        tmp = r.choice(chars)
        if convert_str and (tmp in convert_str):
            tmp = "\\%s" % tmp
        str += tmp
        length -= 1
    return str


def safe_rmdir(path, timeout=10):
    """
    Try to remove a directory safely, even on NFS filesystems.

    Sometimes, when running an autotest client test on an NFS filesystem, when
    not all filedescriptors are closed, NFS will create some temporary files,
    that will make shutil.rmtree to fail with error 39 (directory not empty).
    So let's keep trying for a reasonable amount of time before giving up.

    :param path: Path to a directory to be removed.
    :type path: string
    :param timeout: Time that the function will try to remove the dir before
                    giving up (seconds)
    :type timeout: int
    :raises: OSError, with errno 39 in case after the timeout
             shutil.rmtree could not successfully complete. If any attempt
             to rmtree fails with errno different than 39, that exception
             will be just raised.
    """
    assert os.path.isdir(path), "Invalid directory to remove %s" % path
    step = int(timeout / 10)
    start_time = time.time()
    success = False
    attempts = 0
    while int(time.time() - start_time) < timeout:
        attempts += 1
        try:
            shutil.rmtree(path)
            success = True
            break
        except OSError as err_info:
            # We are only going to try if the error happened due to
            # directory not empty (errno 39). Otherwise, raise the
            # original exception.
            if err_info.errno != 39:
                raise
            time.sleep(step)

    if not success:
        raise OSError(39,
                      "Could not delete directory %s "
                      "after %d s and %d attempts." %
                      (path, timeout, attempts))


def get_archive_tarball_name(source_dir, tarball_name, compression):
    '''
    Get the name for a tarball file, based on source, name and compression
    '''
    if tarball_name is None:
        tarball_name = os.path.basename(source_dir)

    if not tarball_name.endswith('.tar'):
        tarball_name = '%s.tar' % tarball_name

    if compression and not tarball_name.endswith('.%s' % compression):
        tarball_name = '%s.%s' % (tarball_name, compression)

    return tarball_name


def archive_as_tarball(source_dir, dest_dir, tarball_name=None,
                       compression='bz2', verbose=True):
    '''
    Saves the given source directory to the given destination as a tarball

    If the name of the archive is omitted, it will be taken from the
    source_dir. If it is an absolute path, dest_dir will be ignored. But,
    if both the destination directory and tarball anem is given, and the
    latter is not an absolute path, they will be combined.

    For archiving directory '/tmp' in '/net/server/backup' as file
    'tmp.tar.bz2', simply use:

    >>> utils.archive_as_tarball('/tmp', '/net/server/backup')

    To save the file it with a different name, say 'host1-tmp.tar.bz2'
    and save it under '/net/server/backup', use:

    >>> utils.archive_as_tarball('/tmp', '/net/server/backup',
                                 'host1-tmp')

    To save with gzip compression instead (resulting in the file
    '/net/server/backup/host1-tmp.tar.gz'), use:

    >>> utils.archive_as_tarball('/tmp', '/net/server/backup',
                                 'host1-tmp', 'gz')
    '''
    tarball_name = get_archive_tarball_name(source_dir,
                                            tarball_name,
                                            compression)
    if not os.path.isabs(tarball_name):
        tarball_path = os.path.join(dest_dir, tarball_name)
    else:
        tarball_path = tarball_name

    if verbose:
        logging.debug('Archiving %s as %s' % (source_dir,
                                              tarball_path))

    os.chdir(os.path.dirname(source_dir))
    tarball = tarfile.TarFile(name=tarball_path, mode='w')
    tarball = tarball.open(name=tarball_path, mode='w:%s' % compression)
    tarball.add(os.path.basename(source_dir))
    tarball.close()


class VersionableClass(object):

    """
    VersionableClass provides class hierarchy which automatically select right
    version of class. Class manipulation is used for this reason.
    By this reason is:
    Advantage) Only one version is working in one process. Class is changed in
    whole process.
    Disadvantage) Only one version is working in one process.

    Example of usage (in utils_unittest):

    ::

        class FooC(object):
            pass

        #Not implemented get_version -> not used for versioning.
        class VCP(FooC, VersionableClass):
            def __new__(cls, *args, **kargs):
                VCP.master_class = VCP
                return super(VCP, cls).__new__(cls, *args, **kargs)

            def foo(self):
                pass

        class VC2(VCP, VersionableClass):
            @staticmethod
            def get_version():
                return "get_version_from_system"

            @classmethod
            def is_right_version(cls, version):
                if version is not None:
                    if "version is satisfied":
                        return True
                return False

            def func1(self):
                print "func1"

            def func2(self):
                print "func2"

        # get_version could be inherited.
        class VC3(VC2, VersionableClass):
            @classmethod
            def is_right_version(cls, version):
                if version is not None:
                    if "version+1 is satisfied":
                        return True
                return False

            def func2(self):
                print "func2_2"

        class M(VCP):
            pass

        m = M()   # <- When class is constructed the right version is
                  #    automatically selected. In this case VC3 is selected.
        m.func2() # call VC3.func2(m)
        m.func1() # call VC2.func1(m)
        m.foo()   # call VC1.foo(m)

        # When controlled "program" version is changed then is necessary call
         check_repair_versions or recreate object.

        m.check_repair_versions()

        # priority of class. (change place where is method searched first in group
        # of verisonable class.)

        class PP(VersionableClass):
            def __new__(cls, *args, **kargs):
                PP.master_class = PP
                return super(PP, cls).__new__(cls, *args, **kargs)

        class PP2(PP, VersionableClass):
            @staticmethod
            def get_version():
                return "get_version_from_system"

            @classmethod
            def is_right_version(cls, version):
                if version is not None:
                    if "version is satisfied":
                        return True
                return False

            def func1(self):
                print "PP func1"

        class N(VCP, PP):
            pass

        n = N()

        n.func1() # -> "func2"

        n.set_priority_class(PP, [VCP, PP])

        n.func1() # -> "PP func1"

    Necessary for using:
    1) Subclass of versionable class must have implemented class methods
    get_version and is_right_version. These two methods are necessary
    for correct version section. Class without this method will be never
    chosen like suitable class.

    2) Every class derived from master_class have to add to class definition
    inheritance from VersionableClass. Direct inheritance from Versionable
    Class is use like a mark for manipulation with VersionableClass.

    3) Master of VersionableClass have to defined class variable
    cls.master_class.
    """
    def __new__(cls, *args, **kargs):
        cls.check_repair_versions()
        return super(VersionableClass, cls).__new__(cls, *args, **kargs)

    # VersionableClass class management class.

    @classmethod
    def check_repair_versions(cls, master_classes=None):
        """
        Check version of versionable class and if version not
        match repair version to correct version.

        :param master_classes: Check and repair only master_class.
        :type master_classes: list.
        """
        if master_classes is None:
            master_classes = cls._find_versionable_baseclass()
        for base in master_classes:
            cls._check_repair_version_class(base)

    @classmethod
    def set_priority_class(cls, prioritized_class, group_classes):
        """
        Set class priority. Limited only for change bases class priority inside
        one subclass.__bases__ after that continue to another class.
        """
        def change_position(ccls):
            if VersionableClass not in ccls.__bases__:
                bases = list(ccls.__bases__)

                index = None
                remove_variant = None
                for i, item in enumerate(ccls.__bases__):
                    if (VersionableClass in item.__bases__ and
                            item.master_class in group_classes):
                        if index is None:
                            index = i
                        if item.master_class is prioritized_class:
                            remove_variant = item
                            bases.remove(item)
                            break
                else:
                    return

                bases.insert(index, remove_variant)
                ccls.__bases__ = tuple(bases)

        def find_cls(ccls):
            change_position(ccls)
            for base in ccls.__bases__:
                find_cls(base)

        find_cls(cls)

    @classmethod
    def _check_repair_version_class(cls, master_class):
        version = None
        for class_version in master_class._find_versionable_subclass():
            try:
                version = class_version.get_version()
                if class_version.is_right_version(version):
                    cls._switch_by_class(class_version)
                    break
            except NotImplementedError:
                continue
        else:
            cls._switch_by_class(class_version)

    @classmethod
    def _find_versionable_baseclass(cls):
        """
        Find versionable class in master class.
        """
        ver_class = []
        for superclass in cls.mro():
            if VersionableClass in superclass.__bases__:
                ver_class.append(superclass.master_class)

        return set(ver_class)

    @classmethod
    def _find_versionable_subclass(cls):
        """
        Find versionable subclasses which subclass.master_class == cls
        """
        subclasses = [cls]
        for sub in cls.__subclasses__():
            if VersionableClass in list(sub.__bases__):
                subclasses.extend(sub._find_versionable_subclass())
        return subclasses

    @classmethod
    def _switch_by_class(cls, new_class):
        """
        Finds all class with same master_class as new_class in class tree
        and replaces them by new_class.

        :param new_class: Class for replacing.
        """
        def find_replace_class(bases):
            for base in bases:
                if (VersionableClass in base.__bases__ and
                        base.master_class == new_class.master_class):
                    bnew = list(bases)
                    bnew[bnew.index(base)] = new_class
                    return tuple(bnew)
                else:
                    bnew = find_replace_class(base.__bases__)
                    if bnew:
                        base.__bases__ = bnew

        bnew = find_replace_class(cls.__bases__)
        if bnew:
            cls.__bases__ = bnew

    # Method defined in part below must be defined in
    # verisonable class subclass.
    @classmethod
    def get_version(cls):
        """
        Get version of installed OpenVSwtich.
        Must be re-implemented for in child class.

        :return: Version or None when get_version is unsuccessful.
        """
        raise NotImplementedError("Method 'get_verison' must be"
                                  " implemented in child class")

    @classmethod
    def is_right_version(cls, version):
        """
        Check condition for select control class.
        Function must be re-implemented in new OpenVSwitchControl class.
        Must be re-implemented for in child class.

        :param version: version of OpenVSwtich
        """
        raise NotImplementedError("Method 'is_right_version' must be"
                                  " implemented in child class")


if os.path.exists(os.path.join(os.path.dirname(__file__), 'site_utils.py')):
    # Here we are importing site utils only if it exists
    # pylint: disable=E0611
    from autotest.client.shared.site_utils import *

#
# Functions above were imported from virttest/utils_misc.py.
#


def aton(sr):
    """
    Transform a string to a number(include float and int). If the string is
    not in the form of number, just return false.

    :param sr: string to transfrom
    :return: float, int or False for failed transform
    """
    try:
        return int(sr)
    except ValueError:
        try:
            return float(sr)
        except ValueError:
            return False


def find_substring(string, pattern1, pattern2=None):
    """
    Return the match of pattern1 in string. Or return the match of pattern2
    if pattern is not matched.

    @string: string
    @pattern1: first pattern want to match in string, must set.
    @pattern2: second pattern, it will be used if pattern1 not match, optional.

    Return: Match substing or None
    """
    if not pattern1:
        logging.debug("pattern1: get empty string.")
        return None
    pattern = pattern1
    if pattern2:
        pattern += "|%s" % pattern2
    ret = re.findall(pattern, string)
    if not ret:
        logging.debug("Could not find matched string with pattern: %s",
                      pattern)
        return None
    return ret[0]


def lock_file(filename, mode=fcntl.LOCK_EX):
    lockfile = open(filename, "w")
    fcntl.lockf(lockfile, mode)
    return lockfile


def unlock_file(lockfile):
    fcntl.lockf(lockfile, fcntl.LOCK_UN)
    lockfile.close()


# Utility functions for dealing with external processes


def unique(llist):
    """
    Return a list of the elements in list, but without duplicates.

    :param list: List with values.
    :return: List with non duplicate elements.
    """
    n = len(llist)
    if n == 0:
        return []
    u = {}
    try:
        for x in llist:
            u[x] = 1
    except TypeError:
        return None
    else:
        return u.keys()


def find_command(cmd):
    """
    Try to find a command in the PATH, paranoid version.

    :param cmd: Command to be found.
    :raise: ValueError in case the command was not found.
    """
    common_bin_paths = ["/usr/libexec", "/usr/local/sbin", "/usr/local/bin",
                        "/usr/sbin", "/usr/bin", "/sbin", "/bin"]
    try:
        path_paths = os.environ['PATH'].split(":")
    except IndexError:
        path_paths = []
    path_paths = unique(common_bin_paths + path_paths)

    for dir_path in path_paths:
        cmd_path = os.path.join(dir_path, cmd)
        if os.path.isfile(cmd_path):
            return os.path.abspath(cmd_path)

    raise ValueError('Missing command: %s' % cmd)


def pid_exists(pid):
    """
    Return True if a given PID exists.

    :param pid: Process ID number.
    """
    try:
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def safe_kill(pid, signal):
    """
    Attempt to send a signal to a given process that may or may not exist.

    :param signal: Signal number.
    """
    try:
        os.kill(pid, signal)
        return True
    except Exception:
        return False


def kill_process_tree(pid, sig=signal.SIGKILL):
    """Signal a process and all of its children.

    If the process does not exist -- return.

    :param pid: The pid of the process to signal.
    :param sig: The signal to send to the processes.
    """
    if not safe_kill(pid, signal.SIGSTOP):
        return
    children = commands.getoutput("ps --ppid=%d -o pid=" % pid).split()
    for child in children:
        kill_process_tree(int(child), sig)
    safe_kill(pid, sig)
    safe_kill(pid, signal.SIGCONT)


def process_or_children_is_defunct(ppid):
    """Verify if any processes from PPID is defunct.

    Attempt to verify if parent process and any children from PPID is defunct
    (zombie) or not.
    :param ppid: The parent PID of the process to verify.
    """
    defunct = False
    try:
        pids = get_children_pids(ppid)
    except error.CmdError:  # Process doesn't exist
        return True
    for pid in pids:
        cmd = "ps --no-headers -o cmd %d" % int(pid)
        proc_name = system_output(cmd, ignore_status=True)
        if '<defunct>' in proc_name:
            defunct = True
            break
    return defunct


# The following are utility functions related to ports.


def is_port_free(port, address):
    """
    Return True if the given port is available for use.

    :param port: Port number
    """
    try:
        s = socket.socket()
        if address == "localhost":
            s.bind(("localhost", port))
            free = True
        else:
            s.connect((address, port))
            free = False
    except socket.error:
        if address == "localhost":
            free = False
        else:
            free = True
    s.close()
    return free


def find_free_port(start_port, end_port, address="localhost"):
    """
    Return a host free port in the range [start_port, end_port].

    :param start_port: First port that will be checked.
    :param end_port: Port immediately after the last one that will be checked.
    """
    for i in range(start_port, end_port):
        if is_port_free(i, address):
            return i
    return None


def find_free_ports(start_port, end_port, count, address="localhost"):
    """
    Return count of host free ports in the range [start_port, end_port].

    @count: Initial number of ports known to be free in the range.
    :param start_port: First port that will be checked.
    :param end_port: Port immediately after the last one that will be checked.
    """
    ports = []
    i = start_port
    while i < end_port and count > 0:
        if is_port_free(i, address):
            ports.append(i)
            count -= 1
        i += 1
    return ports


# An easy way to log lines to files when the logging system can't be used

_open_log_files = {}
_log_file_dir = "/tmp"


def log_line(filename, line):
    """
    Write a line to a file.  '\n' is appended to the line.

    :param filename: Path of file to write to, either absolute or relative to
            the dir set by set_log_file_dir().
    :param line: Line to write.
    """
    global _open_log_files, _log_file_dir

    path = get_path(_log_file_dir, filename)
    if path not in _open_log_files:
        # First, let's close the log files opened in old directories
        close_log_file(filename)
        # Then, let's open the new file
        try:
            os.makedirs(os.path.dirname(path))
        except OSError:
            pass
        _open_log_files[path] = open(path, "w")
    timestr = time.strftime("%Y-%m-%d %H:%M:%S")
    _open_log_files[path].write("%s: %s\n" % (timestr, line))
    _open_log_files[path].flush()


def set_log_file_dir(directory):
    """
    Set the base directory for log files created by log_line().

    :param dir: Directory for log files.
    """
    global _log_file_dir
    _log_file_dir = directory


def close_log_file(filename):
    global _open_log_files, _log_file_dir
    remove = []
    for k in _open_log_files:
        if os.path.basename(k) == filename:
            f = _open_log_files[k]
            f.close()
            remove.append(k)
    if remove:
        for key_to_remove in remove:
            _open_log_files.pop(key_to_remove)


# The following are miscellaneous utility functions.


def get_path(base_path, user_path):
    """
    Translate a user specified path to a real path.
    If user_path is relative, append it to base_path.
    If user_path is absolute, return it as is.

    :param base_path: The base path of relative user specified paths.
    :param user_path: The user specified path.
    """
    if os.path.isabs(user_path):
        return user_path
    else:
        return os.path.join(base_path, user_path)


def generate_random_id():
    """
    Return a random string suitable for use as a qemu id.
    """
    return "id" + generate_random_string(6)


def generate_tmp_file_name(file_name, ext=None, directory='/tmp/'):
    """
    Returns a temporary file name. The file is not created.
    """
    while True:
        file_name = (file_name + '-' + time.strftime("%Y%m%d-%H%M%S-") +
                     generate_random_string(4))
        if ext:
            file_name += '.' + ext
        file_name = os.path.join(directory, file_name)
        if not os.path.exists(file_name):
            break

    return file_name


def format_str_for_message(msg_str):
    """
    Format msg_str so that it can be appended to a message.
    If msg_str consists of one line, prefix it with a space.
    If msg_str consists of multiple lines, prefix it with a newline.

    :param msg_str: string that will be formatted.
    """
    lines = msg_str.splitlines()
    num_lines = len(lines)
    sr = "\n".join(lines)
    if num_lines == 0:
        return ""
    elif num_lines == 1:
        return " " + sr
    else:
        return "\n" + sr


def wait_for(func, timeout, first=0.0, step=1.0, text=None):
    """
    If func() evaluates to True before timeout expires, return the
    value of func(). Otherwise return None.

    @brief: Wait until func() evaluates to True.

    :param timeout: Timeout in seconds
    :param first: Time to sleep before first attempt
    :param steps: Time to sleep between attempts in seconds
    :param text: Text to print while waiting, for debug purposes
    """
    start_time = time.time()
    end_time = time.time() + timeout

    time.sleep(first)

    while time.time() < end_time:
        if text:
            logging.debug("%s (%f secs)", text, (time.time() - start_time))

        output = func()
        if output:
            return output

        time.sleep(step)

    return None


def get_hash_from_file(hash_path, dvd_basename):
    """
    Get the a hash from a given DVD image from a hash file
    (Hash files are usually named MD5SUM or SHA1SUM and are located inside the
    download directories of the DVDs)

    :param hash_path: Local path to a hash file.
    :param cd_image: Basename of a CD image
    """
    hash_file = open(hash_path, 'r')
    for line in hash_file.readlines():
        if dvd_basename in line:
            return line.split()[0]


def get_full_pci_id(pci_id):
    """
    Get full PCI ID of pci_id.

    :param pci_id: PCI ID of a device.
    """
    cmd = "lspci -D | awk '/%s/ {print $1}'" % pci_id
    status, full_id = commands.getstatusoutput(cmd)
    if status != 0:
        return None
    return full_id


def get_vendor_from_pci_id(pci_id):
    """
    Check out the device vendor ID according to pci_id.

    :param pci_id: PCI ID of a device.
    """
    cmd = "lspci -n | awk '/%s/ {print $3}'" % pci_id
    return re.sub(":", " ", commands.getoutput(cmd))


def parallel(targets):
    """
    Run multiple functions in parallel.

    :param targets: A sequence of tuples or functions.  If it's a sequence of
            tuples, each tuple will be interpreted as (target, args, kwargs) or
            (target, args) or (target,) depending on its length.  If it's a
            sequence of functions, the functions will be called without
            arguments.
    :return: A list of the values returned by the functions called.
    """
    threads = []
    for target in targets:
        if isinstance(target, tuple) or isinstance(target, list):
            t = InterruptedThread(*target)
        else:
            t = InterruptedThread(target)
        threads.append(t)
        t.start()
    return [t.join() for t in threads]


def umount(src, mount_point, fstype, verbose=True, fstype_mtab=None):
    """
    Umount the src mounted in mount_point.

    :src: mount source
    :mount_point: mount point
    :type: file system type
    :param fstype_mtab: file system type in mtab could be different
    :type fstype_mtab: str
    """
    if fstype_mtab is None:
        fstype_mtab = fstype

    if is_mounted(src, mount_point, fstype, None, verbose, fstype_mtab):
        umount_cmd = "umount %s" % mount_point
        try:
            system(umount_cmd, verbose)
            return True
        except error.CmdError:
            return False
    else:
        logging.debug("%s is not mounted under %s", src, mount_point)
        return True


def mount(src, mount_point, fstype, perm=None, verbose=True, fstype_mtab=None):
    """
    Mount the src into mount_point of the host.

    :src: mount source
    :mount_point: mount point
    :fstype: file system type
    :perm: mount permission
    :param fstype_mtab: file system type in mtab could be different
    :type fstype_mtab: str
    """
    if perm is None:
        perm = "rw"
    if fstype_mtab is None:
        fstype_mtab = fstype

    umount(src, mount_point, fstype, verbose, fstype_mtab)

    if is_mounted(src, mount_point, fstype, perm, verbose, fstype_mtab):
        logging.debug("%s is already mounted in %s with %s",
                      src, mount_point, perm)
        return True

    mount_cmd = "mount -t %s %s %s -o %s" % (fstype, src, mount_point, perm)
    try:
        system(mount_cmd, verbose=verbose)
    except error.CmdError:
        return False

    return is_mounted(src, mount_point, fstype, perm, verbose, fstype_mtab)


def is_mounted(src, mount_point, fstype, perm=None, verbose=True,
               fstype_mtab=None):
    """
    Check mount status from /etc/mtab

    :param src: mount source
    :type src: string
    :param mount_point: mount point
    :type mount_point: string
    :param fstype: file system type
    :type fstype: string
    :param perm: mount permission
    :type perm: string
    :param fstype_mtab: file system type in mtab could be different
    :type fstype_mtab: str
    :return: if the src is mounted as expect
    :rtype: Boolean
    """
    if perm is None:
        perm = ""
    if fstype_mtab is None:
        fstype_mtab = fstype

    mount_point = os.path.realpath(mount_point)
    if fstype not in ['nfs', 'smbfs', 'glusterfs', 'hugetlbfs', 'ubifs']:
        if src:
            src = os.path.realpath(src)
        else:
            # Allow no passed src(None or "")
            src = ""
    mount_string = "%s %s %s %s" % (src, mount_point, fstype_mtab, perm)
    if mount_string.strip() in file("/etc/mtab").read():
        logging.debug("%s is successfully mounted", src)
        return True
    else:
        if verbose:
            logging.error("Can't find mounted NFS share - /etc/mtab"
                          " contents \n%s", file("/etc/mtab").read())
        return False


def bitlist_to_string(data):
    """
    Transform from bit list to ASCII string.

    :param data: Bit list to be transformed
    """
    result = []
    pos = 0
    c = 0
    while pos < len(data):
        c += data[pos] << (7 - (pos % 8))
        if (pos % 8) == 7:
            result.append(c)
            c = 0
        pos += 1
    return ''.join([chr(c) for c in result])


def string_to_bitlist(data):
    """
    Transform from ASCII string to bit list.

    :param data: String to be transformed
    """
    data = [ord(c) for c in data]
    result = []
    for ch in data:
        i = 7
        while i >= 0:
            if ch & (1 << i) != 0:
                result.append(1)
            else:
                result.append(0)
            i -= 1
    return result


def strip_console_codes(output):
    """
    Remove the Linux console escape and control sequences from the console
    output. Make the output readable and can be used for result check. Now
    only remove some basic console codes using during boot up.

    :param output: The output from Linux console
    :type output: string
    :return: the string wihout any special codes
    :rtype: string
    """
    if "\x1b" not in output:
        return output

    old_word = ""
    return_str = ""
    index = 0
    output = "\x1b[m%s" % output
    console_codes = "%G|\[m|\[[\d;]+[HJnrm]"
    while index < len(output):
        tmp_index = 0
        tmp_word = ""
        while (len(re.findall("\x1b", tmp_word)) < 2 and
               index + tmp_index < len(output)):
            tmp_word += output[index + tmp_index]
            tmp_index += 1

        tmp_word = re.sub("\x1b", "", tmp_word)
        index += len(tmp_word) + 1
        if tmp_word == old_word:
            continue
        try:
            special_code = re.findall(console_codes, tmp_word)[0]
        except IndexError:
            if index + tmp_index < len(output):
                raise ValueError("%s is not included in the known console "
                                 "codes list %s" % (tmp_word, console_codes))
            continue
        if special_code == tmp_word:
            continue
        old_word = tmp_word
        return_str += tmp_word[len(special_code):]
    return return_str


def create_x509_dir(path, cacert_subj, server_subj, passphrase,
                    secure=False, bits=1024, days=1095):
    """
    Creates directory with freshly generated:
    ca-cart.pem, ca-key.pem, server-cert.pem, server-key.pem,

    :param path: defines path to directory which will be created
    :param cacert_subj: ca-cert.pem subject
    :param server_key.csr subject
    :param passphrase - passphrase to ca-key.pem
    :param secure = False - defines if the server-key.pem will use a passphrase
    :param bits = 1024: bit length of keys
    :param days = 1095: cert expiration

    :raise ValueError: openssl not found or rc != 0
    :raise OSError: if os.makedirs() fails
    """

    ssl_cmd = os_dep.command("openssl")
    path = path + os.path.sep  # Add separator to the path
    shutil.rmtree(path, ignore_errors=True)
    os.makedirs(path)

    server_key = "server-key.pem.secure"
    if secure:
        server_key = "server-key.pem"

    cmd_set = [
        ('%s genrsa -des3 -passout pass:%s -out %sca-key.pem %d' %
         (ssl_cmd, passphrase, path, bits)),
        ('%s req -new -x509 -days %d -key %sca-key.pem -passin pass:%s -out '
         '%sca-cert.pem -subj "%s"' %
         (ssl_cmd, days, path, passphrase, path, cacert_subj)),
        ('%s genrsa -out %s %d' % (ssl_cmd, path + server_key, bits)),
        ('%s req -new -key %s -out %s/server-key.csr -subj "%s"' %
         (ssl_cmd, path + server_key, path, server_subj)),
        ('%s x509 -req -passin pass:%s -days %d -in %sserver-key.csr -CA '
         '%sca-cert.pem -CAkey %sca-key.pem -set_serial 01 -out %sserver-cert.pem' %
         (ssl_cmd, passphrase, days, path, path, path, path))
    ]

    if not secure:
        cmd_set.append('%s rsa -in %s -out %sserver-key.pem' %
                       (ssl_cmd, path + server_key, path))

    for cmd in cmd_set:
        run(cmd)
        logging.info(cmd)


def convert_ipv4_to_ipv6(ipv4):
    """
    Translates a passed in string of an ipv4 address to an ipv6 address.

    :param ipv4: a string of an ipv4 address
    """

    converted_ip = "::ffff:"
    split_ipaddress = ipv4.split('.')
    try:
        socket.inet_aton(ipv4)
    except socket.error:
        raise ValueError("ipv4 to be converted is invalid")
    if (len(split_ipaddress) != 4):
        raise ValueError("ipv4 address is not in dotted quad format")

    for index, string in enumerate(split_ipaddress):
        if index != 1:
            test = str(hex(int(string)).split('x')[1])
            if len(test) == 1:
                final = "0"
                final += test
                test = final
        else:
            test = str(hex(int(string)).split('x')[1])
            if len(test) == 1:
                final = "0"
                final += test + ":"
                test = final
            else:
                test += ":"
        converted_ip += test
    return converted_ip


def get_thread_cpu(thread):
    """
    Get the light weight process(thread) used cpus.

    :param thread: thread checked
    :type thread: string
    :return: A list include all cpus the thread used
    :rtype: list
    """
    cmd = "ps -o cpuid,lwp -eL | grep -w %s$" % thread
    cpu_thread = system_output(cmd)
    if not cpu_thread:
        return []
    return list(set([_.strip().split()[0] for _ in cpu_thread.splitlines()]))


def get_pid_cpu(pid):
    """
    Get the process used cpus.

    :param pid: process id
    :type thread: string
    :return: A list include all cpus the process used
    :rtype: list
    """
    cmd = "ps -o cpuid -L -p %s" % pid
    cpu_pid = system_output(cmd)
    if not cpu_pid:
        return []
    return list(set([_.strip() for _ in cpu_pid.splitlines()]))


def verify_running_as_root():
    """
    Verifies whether we're running under UID 0 (root).

    :raise: error.TestNAError
    """
    if os.getuid() != 0:
        raise error.TestNAError("This test requires root privileges "
                                "(currently running with user %s)" %
                                getpass.getuser())


def selinux_enforcing():
    """
    Returns True if SELinux is in enforcing mode, False if permissive/disabled
    """
    cmdresult = run('getenforce', ignore_status=True, verbose=False)
    mobj = re.search('Enforcing', cmdresult.stdout)
    return mobj is not None


def get_unique_name(check, prefix="", suffix="", length=None, skip=None):
    """
    Get unique name according to check function, use only 1000 iterations.
    :param cmp: Function called to discover name uniqueness
    :param prefix: Name prefix
    :param suffix: Name suffix
    :param length: Length of random string, when None use numbers (0,1,2)
    :param skip: skip n numbers (only when length=None

    :raise StopIteration: In case no unique name obtained in 1000 iterations
    :return: Unique name according to check function
    """
    if length:
        _name = "_".join([_ for _ in (prefix, '%s', suffix) if _])
        for _ in xrange(1000):
            name = _name % generate_random_string(length)
            if check(name):
                return name
    else:
        _name = "_".join([_ for _ in (prefix, '%s', suffix) if _])
        for i in xrange(skip, skip + 1000):
            name = _name % i
            if check(name):
                return name
    raise StopIteration("Fail to get unique name in 1000 iterations. (%s)"
                        % _name)
