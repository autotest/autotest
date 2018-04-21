import cPickle as pickle
import copy
import errno
import fcntl
import logging
import os
import re
import tarfile
import time
import traceback
import weakref

from autotest.client.shared import autotemp, error, log
from autotest.client.shared.settings import settings

# Mapping between job statuses and whether the operation is OK or not
JOB_STATUSES = {"TEST_NA": False,
                "END TEST_NA": False,
                "ABORT": False,
                "END ABORT": False,
                "ERROR": False,
                "END ERROR": False,
                "FAIL": False,
                "END FAIL": False,
                "WARN": False,
                "END WARN": False,
                "BUG": True,
                "END BUG": True,
                "GOOD": True,
                "END GOOD": True,
                "START": True,
                "ALERT": False,
                "RUNNING": False,
                "NOSTATUS": False}


class job_directory(object):
    """Represents a job.*dir directory."""

    class JobDirectoryException(error.AutotestError):

        """Generic job_directory exception superclass."""

    class MissingDirectoryException(JobDirectoryException):

        """Raised when a directory required by the job does not exist."""

        def __init__(self, path):
            Exception.__init__(self, 'Directory %s does not exist' % path)

    class UncreatableDirectoryException(JobDirectoryException):

        """Raised when a directory required by the job is missing and cannot
        be created."""

        def __init__(self, path, error):
            msg = 'Creation of directory %s failed with exception %s'
            msg %= (path, error)
            Exception.__init__(self, msg)

    class UnwritableDirectoryException(JobDirectoryException):

        """Raised when a writable directory required by the job exists
        but is not writable."""

        def __init__(self, path):
            msg = 'Directory %s exists but is not writable' % path
            Exception.__init__(self, msg)

    def __init__(self, path, is_writable=False):
        """
        Instantiate a job directory.

        :param path: The path of the directory. If None a temporary directory
                     will be created instead.
        :type path: string

        :param is_writable: If True, expect the directory to be writable.
        :type is_writable: bool

        :raises: :class:`MissingDirectoryException` if ``is_writable=False``
                 and the directory does not exist.
        :raises: :class:`UnwritableDirectoryException` if ``is_writable=True``
                 and the directory exists but is not writable.
        :raises: :class:`UncreatableDirectoryException` if ``is_writable=True``
                 the directory does not exist and it cannot be created.
        """
        if path is None:
            if is_writable:
                self._tempdir = autotemp.tempdir(unique_id='autotest')
                self.path = self._tempdir.name
            else:
                raise self.MissingDirectoryException(path)
        else:
            self._tempdir = None
            self.path = path
        self._ensure_valid(is_writable)

    def _ensure_valid(self, is_writable):
        """
        Ensure that this is a valid directory.

        Will check if a directory exists, can optionally also enforce that
        it be writable. It can optionally create it if necessary. Creation
        will still fail if the path is rooted in a non-writable directory, or
        if a file already exists at the given location.

        :param is_writable: A boolean indicating that the directory should
                            not only exist, but also be writable.
        :type is_writable: bool

        :raises: :class:`MissingDirectoryException` if ``is_writable=False``
                 and the directory does not exist.
        :raises: :class:`UnwritableDirectoryException` if ``is_writable=True``
                 and the directory is not wrtiable.
        :raises: :class:`UncreatableDirectoryException` if ``is_writable=True``
                 the directory does not exist and it cannot be created
        """
        # ensure the directory exists
        if is_writable:
            try:
                os.makedirs(self.path)
            except OSError, e:
                if e.errno != errno.EEXIST or not os.path.isdir(self.path):
                    raise self.UncreatableDirectoryException(self.path, e)
        elif not os.path.isdir(self.path):
            raise self.MissingDirectoryException(self.path)

        # if is_writable=True, also check that the directory is writable
        if is_writable and not os.access(self.path, os.W_OK):
            raise self.UnwritableDirectoryException(self.path)

    @staticmethod
    def property_factory(attribute):
        """
        Create a job.*dir -> job._*dir.path property accessor.

        :param attribute: A string with the name of the attribute this is
                          exposed as. '_'+attribute must then be attribute
                          that holds either None or a job_directory-like object

        :returns: A read-only property object that exposes a job_directory path
        """

        @property
        def dir_property(self):
            underlying_attribute = getattr(self, '_' + attribute)
            if underlying_attribute is None:
                return None
            else:
                return underlying_attribute.path

        return dir_property


# decorator for use with job_state methods
def with_backing_lock(method):
    """
    A decorator to perform a lock-*-unlock cycle.

    When applied to a method, this decorator will automatically wrap
    calls to the method in a backing file lock and before the call
    followed by a backing file unlock.
    """

    def wrapped_method(self, *args, **dargs):
        already_have_lock = self._backing_file_lock is not None
        if not already_have_lock:
            self._lock_backing_file()
        try:
            return method(self, *args, **dargs)
        finally:
            if not already_have_lock:
                self._unlock_backing_file()

    wrapped_method.__name__ = method.__name__
    wrapped_method.__doc__ = method.__doc__
    return wrapped_method


# decorator for use with job_state methods
def with_backing_file(method):
    """
    A decorator to perform a lock-read-*-write-unlock cycle.

    When applied to a method, this decorator will automatically wrap
    calls to the method in a lock-and-read before the call followed by a
    write-and-unlock. Any operation that is reading or writing state
    should be decorated with this method to ensure that backing file
    state is consistently maintained.
    """

    @with_backing_lock
    def wrapped_method(self, *args, **dargs):
        self._read_from_backing_file()
        try:
            return method(self, *args, **dargs)
        finally:
            self._write_to_backing_file()

    wrapped_method.__name__ = method.__name__
    wrapped_method.__doc__ = method.__doc__
    return wrapped_method


class job_state(object):
    """
    A class for managing explicit job and user state, optionally persistent.

    The class allows you to save state by name (like a dictionary). Any state
    stored in this class should be picklable and deep copyable. While this is
    not enforced it is recommended that only valid python identifiers be used
    as names. Additionally, the namespace 'stateful_property' is used for
    storing the valued associated with properties constructed using the
    property_factory method.
    """

    NO_DEFAULT = object()
    PICKLE_PROTOCOL = 2  # highest protocol available in python 2.4

    def __init__(self):
        """Initialize the job state."""
        self._state = {}
        self._backing_file = None
        self._backing_file_initialized = False
        self._backing_file_lock = None

    def _lock_backing_file(self):
        """Acquire a lock on the backing file."""
        if self._backing_file:
            self._backing_file_lock = open(self._backing_file, 'a')
            fcntl.flock(self._backing_file_lock, fcntl.LOCK_EX)

    def _unlock_backing_file(self):
        """Release a lock on the backing file."""
        if self._backing_file_lock:
            fcntl.flock(self._backing_file_lock, fcntl.LOCK_UN)
            self._backing_file_lock.close()
            self._backing_file_lock = None

    def read_from_file(self, file_path, merge=True):
        """
        Read in any state from the file at file_path.

        When ``merge=True``, any state specified only in-memory will be
        preserved. Any state specified on-disk will be set in-memory, even if an
        in-memory setting already exists.

        :param file_path: The path where the state should be read from. It must
                          exist but it can be empty.
        :type file_path: string

        :param merge: If true, merge the on-disk state with the in-memory
                      state. If false, replace the in-memory state with the
                      on-disk state.
        :type merge: bool

        Warning: This method is intentionally concurrency-unsafe. It makes no
        attempt to control concurrent access to the file at ``file_path``.
        """

        # we can assume that the file exists
        if os.path.getsize(file_path) == 0:
            on_disk_state = {}
        else:
            on_disk_state = pickle.load(open(file_path))

        if merge:
            # merge the on-disk state with the in-memory state
            for namespace, namespace_dict in on_disk_state.iteritems():
                in_memory_namespace = self._state.setdefault(namespace, {})
                for name, value in namespace_dict.iteritems():
                    if name in in_memory_namespace:
                        if in_memory_namespace[name] != value:
                            logging.info('Persistent value of %s.%s from %s '
                                         'overridding existing in-memory '
                                         'value', namespace, name, file_path)
                            in_memory_namespace[name] = value
                        else:
                            logging.debug('Value of %s.%s is unchanged, '
                                          'skipping import', namespace, name)
                    else:
                        logging.debug('Importing %s.%s from state file %s',
                                      namespace, name, file_path)
                        in_memory_namespace[name] = value
        else:
            # just replace the in-memory state with the on-disk state
            self._state = on_disk_state

        # lock the backing file before we refresh it
        with_backing_lock(self.__class__._write_to_backing_file)(self)

    def write_to_file(self, file_path):
        """
        Write out the current state to the given path.

        Warning: This method is intentionally concurrency-unsafe. It makes no
        attempt to control concurrent access to the file at file_path.

        :param file_path: The path where the state should be written out to.
                          Must be writable.
        :type file_path: string
        """
        outfile = open(file_path, 'w')
        try:
            pickle.dump(self._state, outfile, self.PICKLE_PROTOCOL)
        finally:
            outfile.close()

    def _read_from_backing_file(self):
        """
        Refresh the current state from the backing file.

        If the backing file has never been read before (indicated by checking
        self._backing_file_initialized) it will merge the file with the
        in-memory state, rather than overwriting it.
        """
        if self._backing_file:
            merge_backing_file = not self._backing_file_initialized
            self.read_from_file(self._backing_file, merge=merge_backing_file)
            self._backing_file_initialized = True

    def _write_to_backing_file(self):
        """Flush the current state to the backing file."""
        if self._backing_file:
            self.write_to_file(self._backing_file)

    @with_backing_file
    def _synchronize_backing_file(self):
        """
        Synchronizes the contents of the in-memory and on-disk state.
        """
        # state is implicitly synchronized in _with_backing_file methods
        pass

    def set_backing_file(self, file_path):
        """
        Change the path used as the backing file for the persistent state.

        When a new backing file is specified if a file already exists then
        its contents will be added into the current state, with conflicts
        between the file and memory being resolved in favor of the file
        contents. The file will then be kept in sync with the (combined)
        in-memory state. The syncing can be disabled by setting this to None.

        :param file_path: A path on the filesystem that can be read from and
                          written to, or None to turn off the backing store.
        :type file_path: string
        """
        self._synchronize_backing_file()
        self._backing_file = file_path
        self._backing_file_initialized = False
        self._synchronize_backing_file()

    @with_backing_file
    def get(self, namespace, name, default=NO_DEFAULT):
        """
        Returns the value associated with a particular name.

        :param namespace: The namespace that the property should be stored in.
        :type namespace: string

        :param name: The name the value was saved with.
        :type name: string

        :param default: A default value to return if no state is currently
                        associated with var.
        :type default: object

        :returns: A deep copy of the value associated with name. Note that this
                  explicitly returns a deep copy to avoid problems with mutable
                  values; mutations are not persisted or shared.

        :raises: :class:`KeyError` raised when no state is associated with var
                 and a default value is not provided.
        """
        if self.has(namespace, name):
            return copy.deepcopy(self._state[namespace][name])
        elif default is self.NO_DEFAULT:
            raise KeyError('No key %s in namespace %s' % (name, namespace))
        else:
            return default

    @with_backing_file
    def set(self, namespace, name, value):
        """
        Saves the value given with the provided name.

        :param namespace: The namespace that the property should be stored in.
        :type namespace: string

        :param name: The name the value was saved with.
        :type name: string

        :param value: The value to save.
        """
        namespace_dict = self._state.setdefault(namespace, {})
        namespace_dict[name] = copy.deepcopy(value)
        logging.debug('Persistent state %s.%s now set to %r', namespace,
                      name, value)

    @with_backing_file
    def has(self, namespace, name):
        """
        Return a boolean indicating if namespace.name is defined.

        :param namespace: The namespace that the property should be stored in.
        :type namespace: string

        :param name: The name the value was saved with.
        :type name: string

        :returns: True if the given name is defined in the given namespace and
                  False otherwise.
        :rtype: bool
        """
        return namespace in self._state and name in self._state[namespace]

    @with_backing_file
    def discard(self, namespace, name):
        """
        If namespace.name is a defined value, deletes it.

        :param namespace: The namespace that the property should be stored in.
        :type namespace: string

        :param name: The name the value was saved with.
        :type name: string
        """
        if self.has(namespace, name):
            del self._state[namespace][name]
            if len(self._state[namespace]) == 0:
                del self._state[namespace]
            logging.debug('Persistent state %s.%s deleted', namespace, name)
        else:
            logging.debug(
                'Persistent state %s.%s not defined so nothing is discarded',
                namespace, name)

    @with_backing_file
    def discard_namespace(self, namespace):
        """
        Delete all defined namespace.* names.

        :param namespace: The namespace to be cleared.
        :type namespace: string
        """
        if namespace in self._state:
            del self._state[namespace]
        logging.debug('Persistent state %s.* deleted', namespace)

    @staticmethod
    def property_factory(state_attribute, property_attribute, default,
                         namespace='global_properties'):
        """
        Create a property object for an attribute using self.get and self.set.

        :param state_attribute: A string with the name of the attribute on
                                job that contains the job_state instance.

        :param property_attribute: A string with the name of the attribute
                                   this property is exposed as.

        :param default: A default value that should be used for this property
                        if it is not set.

        :param namespace: The namespace to store the attribute value in.

        :returns: A read-write property object that performs self.get calls
                  to read the value and self.set calls to set it.
        """

        def getter(job):
            state = getattr(job, state_attribute)
            return state.get(namespace, property_attribute, default)

        def setter(job, value):
            state = getattr(job, state_attribute)
            state.set(namespace, property_attribute, value)

        return property(getter, setter)


class status_log_entry(object):
    """
    Represents a single status log entry.
    """

    RENDERED_NONE_VALUE = '----'
    TIMESTAMP_FIELD = 'timestamp'
    LOCALTIME_FIELD = 'localtime'

    # non-space whitespace is forbidden in any fields
    BAD_CHAR_REGEX = re.compile(r'[\t\n\r\v\f]')

    def __init__(self, status_code, subdir, operation, message, fields,
                 timestamp=None):
        """
        Construct a status.log entry.

        :param status_code: A message status code. Must match the codes
                            accepted by autotest.shared.log.is_valid_status.

        :param subdir: A valid job subdirectory, or None.

        :param operation: Description of the operation, or None.

        :param message: A printable string describing event to be recorded.

        :param fields: A dictionary of arbitrary alphanumeric key=value pairs
                       to be included in the log, or None.

        :param timestamp: An optional integer timestamp, in the same format
                          as a time.time() timestamp. If unspecified, the
                          current time is used.

        :raises: :class:`ValueError` if any of the parameters are invalid
        """
        if not log.is_valid_status(status_code):
            raise ValueError('status code %r is not valid' % status_code)
        self.status_code = status_code

        if subdir and self.BAD_CHAR_REGEX.search(subdir):
            raise ValueError('Invalid character in subdir string')
        self.subdir = subdir

        if operation and self.BAD_CHAR_REGEX.search(operation):
            raise ValueError('Invalid character in operation string')
        self.operation = operation

        # break the message line into a single-line message that goes into the
        # database, and a block of additional lines that goes into the status
        # log but will never be parsed
        message_lines = message.split('\n')
        self.message = message_lines[0].replace('\t', ' ' * 8)
        self.extra_message_lines = message_lines[1:]
        if self.BAD_CHAR_REGEX.search(self.message):
            raise ValueError('Invalid character in message %r' % self.message)

        if not fields:
            self.fields = {}
        else:
            self.fields = fields.copy()
        for key, value in self.fields.iteritems():
            if type(value) is int:
                value = str(value)
            if self.BAD_CHAR_REGEX.search(key + value):
                raise ValueError('Invalid character in %r=%r field'
                                 % (key, value))

        # build up the timestamp
        if timestamp is None:
            timestamp = int(time.time())
        self.fields[self.TIMESTAMP_FIELD] = str(timestamp)
        self.fields[self.LOCALTIME_FIELD] = time.strftime(
            '%b %d %H:%M:%S', time.localtime(timestamp))

    def is_start(self):
        """
        Indicates if this status log is the start of a new nested block.

        :returns: A boolean indicating if this entry starts a new nested block.
        """
        return self.status_code == 'START'

    def is_end(self):
        """
        Indicates if this status log is the end of a nested block.

        :returns: A boolean indicating if this entry ends a nested block.
        """
        return self.status_code.startswith('END ')

    def render(self):
        """
        Render the status log entry into a text string.

        :returns: A text string suitable for writing into a status log file.
        """
        # combine all the log line data into a tab-delimited string
        subdir = self.subdir or self.RENDERED_NONE_VALUE
        operation = self.operation or self.RENDERED_NONE_VALUE
        extra_fields = ['%s=%s' % field for field in self.fields.iteritems()]
        line_items = [self.status_code, subdir, operation]
        line_items += extra_fields + [self.message]
        first_line = '\t'.join(line_items)

        # append the extra unparsable lines, two-space indented
        all_lines = [first_line]
        all_lines += ['  ' + line for line in self.extra_message_lines]
        return '\n'.join(all_lines)

    @classmethod
    def parse(cls, line):
        """
        Parse a status log entry from a text string.

        This method is the inverse of render; it should always be true that
        parse(entry.render()) produces a new status_log_entry equivalent to
        entry.

        :returns: A new status_log_entry instance with fields extracted from
                  the given status line. If the line is an extra message line
                  then None is returned.
        """
        # extra message lines are always prepended with two spaces
        if line.startswith('  '):
            return None

        line = line.lstrip('\t')  # ignore indentation
        entry_parts = line.split('\t')
        if len(entry_parts) < 4:
            raise ValueError('%r is not a valid status line' % line)
        status_code, subdir, operation = entry_parts[:3]
        if subdir == cls.RENDERED_NONE_VALUE:
            subdir = None
        if operation == cls.RENDERED_NONE_VALUE:
            operation = None
        message = entry_parts[-1]
        fields = dict(part.split('=', 1) for part in entry_parts[3:-1])
        if cls.TIMESTAMP_FIELD in fields:
            timestamp = int(fields[cls.TIMESTAMP_FIELD])
        else:
            timestamp = None
        return cls(status_code, subdir, operation, message, fields, timestamp)


class status_indenter(object):
    """
    Abstract interface that a status log indenter should use.
    """

    @property
    def indent(self):
        raise NotImplementedError

    def increment(self):
        """Increase indentation by one level."""
        raise NotImplementedError

    def decrement(self):
        """Decrease indentation by one level."""


class status_logger(object):
    """
    Represents a status log file. Responsible for translating messages
    into on-disk status log lines.

    :property global_filename: The filename to write top-level logs to.
    :property subdir_filename: The filename to write subdir-level logs to.
    """

    def __init__(self, job, indenter, global_filename='status',
                 subdir_filename='status', record_hook=None,
                 tap_writer=None):
        """
        Construct a logger instance.

        :param job: A reference to the job object this is logging for. Only a
                    weak reference to the job is held, to avoid a status_logger
                    <-> job circular reference.

        :param indenter: A status_indenter instance, for tracking the
                         indentation level.

        :param global_filename: An optional filename to initialize the
                                ``self.global_filename`` attribute.

        :param subdir_filename: An optional filename to initialize the
                                ``self.subdir_filename`` attribute.

        :param record_hook: An optional function to be called before an entry
                            is logged. The function should expect a single
                            parameter, a copy of the status_log_entry object.

        :param tap_writer: An instance of the class TAPReport for addionally
                           writing TAP files
        """
        self._jobref = weakref.ref(job)
        self._indenter = indenter
        self.global_filename = global_filename
        self.subdir_filename = subdir_filename
        self._record_hook = record_hook
        if tap_writer is None:
            self._tap_writer = TAPReport(None)
        else:
            self._tap_writer = tap_writer

    def render_entry(self, log_entry):
        """
        Render a status_log_entry as it would be written to a log file.

        :param log_entry: A status_log_entry instance to be rendered.

        :returns: The status log entry, rendered as it would be written to the
                  logs (including indentation).
        """
        if log_entry.is_end():
            indent = self._indenter.indent - 1
        else:
            indent = self._indenter.indent
        return '\t' * indent + log_entry.render().rstrip('\n')

    def record_entry(self, log_entry, log_in_subdir=True):
        """
        Record a status_log_entry into the appropriate status log files.

        :param log_entry: A status_log_entry instance to be recorded into the
                          status logs.
        :param log_in_subdir: A boolean that indicates (when true) that subdir
                              logs should be written into the subdirectory status
                              log file.
        """
        # acquire a strong reference for the duration of the method
        job = self._jobref()
        if job is None:
            logging.warning('Something attempted to write a status log entry '
                            'after its job terminated, ignoring the attempt.')
            logging.warning(traceback.format_stack())
            return

        # call the record hook if one was given
        if self._record_hook:
            self._record_hook(log_entry)

        # figure out where we need to log to
        log_files = [os.path.join(job.resultdir, self.global_filename)]
        if log_in_subdir and log_entry.subdir:
            log_files.append(os.path.join(job.resultdir, log_entry.subdir,
                                          self.subdir_filename))

        # write out to entry to the log files
        log_text = self.render_entry(log_entry)
        for log_file in log_files:
            fileobj = open(log_file, 'a')
            try:
                print(log_text, file=fileobj)
            finally:
                fileobj.close()

        # write to TAPRecord instance
        if log_entry.is_end() and self._tap_writer.do_tap_report:
            self._tap_writer.record(log_entry, self._indenter.indent, log_files)

        # adjust the indentation if this was a START or END entry
        if log_entry.is_start():
            self._indenter.increment()
        elif log_entry.is_end():
            self._indenter.decrement()


class TAPReport(object):
    """
    Deal with TAP reporting for the Autotest client.
    """

    job_statuses = {
        "TEST_NA": False,
        "ABORT": False,
        "ERROR": False,
        "FAIL": False,
        "WARN": False,
        "GOOD": True,
        "START": True,
        "END GOOD": True,
        "ALERT": False,
        "RUNNING": False,
        "NOSTATUS": False
    }

    def __init__(self, enable, resultdir=None, global_filename='status'):
        """
        :param enable: Set self.do_tap_report to trigger TAP reporting.
        :param resultdir: Path where the TAP report files will be written.
        :param global_filename: File name of the status files .tap extensions
                                will be appended.
        """
        self.do_tap_report = enable
        if resultdir is not None:
            self.resultdir = os.path.abspath(resultdir)
        self._reports_container = {}
        self._keyval_container = {}  # {'path1': [entries],}
        self.global_filename = global_filename

    @classmethod
    def tap_ok(self, success, counter, message):
        """
        return a TAP message string.

        :param success: True for positive message string.
        :param counter: number of TAP line in plan.
        :param message: additional message to report in TAP line.
        """
        if success:
            message = "ok %s - %s" % (counter, message)
        else:
            message = "not ok %s - %s" % (counter, message)
        return message

    def record(self, log_entry, indent, log_files):
        """
        Append a job-level status event to self._reports_container. All
        events will be written to TAP log files at the end of the test run.
        Otherwise, it's impossilble to determine the TAP plan.

        :param log_entry: A string status code describing the type of status
                entry being recorded. It must pass log.is_valid_status to be
                considered valid.
        :param indent: Level of the log_entry to determine the operation if
                log_entry.operation is not given.
        :param log_files: List of full path of files the TAP report will be
                written to at the end of the test.
        """
        for log_file in log_files:
            log_file_path = os.path.dirname(log_file)
            key = log_file_path.split(self.resultdir, 1)[1].strip(os.sep)
            if not key:
                key = 'root'

            if key not in self._reports_container:
                self._reports_container[key] = []

            if log_entry.operation:
                operation = log_entry.operation
            elif indent == 1:
                operation = "job"
            else:
                operation = "unknown"
            entry = self.tap_ok(
                JOB_STATUSES.get(log_entry.status_code, False),
                len(self._reports_container[key]) + 1, operation + "\n"
            )
            self._reports_container[key].append(entry)

    def record_keyval(self, path, dictionary, type_tag=None):
        """
        Append a key-value pairs of dictionary to self._keyval_container in
        TAP format. Once finished write out the keyval.tap file to the file
        system.

        If type_tag is None, then the key must be composed of alphanumeric
        characters (or dashes + underscores). However, if type-tag is not
        null then the keys must also have "{type_tag}" as a suffix. At
        the moment the only valid values of type_tag are "attr" and "perf".

        :param path: The full path of the keyval.tap file to be created
        :param dictionary: The keys and values.
        :param type_tag: The type of the values
        """
        self._keyval_container.setdefault(path, [0, []])
        self._keyval_container[path][0] += 1

        if type_tag is None:
            key_regex = re.compile(r'^[-\.\w]+$')
        else:
            if type_tag not in ('attr', 'perf'):
                raise ValueError('Invalid type tag: %s' % type_tag)
            escaped_tag = re.escape(type_tag)
            key_regex = re.compile(r'^[-\.\w]+\{%s\}$' % escaped_tag)
        self._keyval_container[path][1].extend([
            self.tap_ok(True, self._keyval_container[path][0], "results"),
            "\n  ---\n",
        ])
        try:
            for key in sorted(dictionary.keys()):
                if not key_regex.search(key):
                    raise ValueError('Invalid key: %s' % key)
                self._keyval_container[path][1].append(
                    '  %s: %s\n' % (key.replace('{', '_').rstrip('}'),
                                    dictionary[key])
                )
        finally:
            self._keyval_container[path][1].append("  ...\n")
        self._write_keyval()

    def _write_reports(self):
        """
        Write TAP reports to file.
        """
        for key in self._reports_container.keys():
            if key == 'root':
                sub_dir = ''
            else:
                sub_dir = key
            tap_fh = open(os.sep.join(
                [self.resultdir, sub_dir, self.global_filename]
            ) + ".tap", 'w')
            tap_fh.write('1..' + str(len(self._reports_container[key])) + '\n')
            tap_fh.writelines(self._reports_container[key])
            tap_fh.close()

    def _write_keyval(self):
        """
        Write the self._keyval_container key values to a file.
        """
        for path in self._keyval_container.keys():
            tap_fh = open(path + ".tap", 'w')
            tap_fh.write('1..' + str(self._keyval_container[path][0]) + '\n')
            tap_fh.writelines(self._keyval_container[path][1])
            tap_fh.close()

    def write(self):
        """
        Write the TAP reports to files.
        """
        self._write_reports()

    def _write_tap_archive(self):
        """
        Write a tar archive containing all the TAP files and
        a meta.yml containing the file names.
        """
        os.chdir(self.resultdir)
        tap_files = []
        for rel_path, _, files in os.walk('.'):
            tap_files.extend(["/".join(
                [rel_path, f]) for f in files if f.endswith('.tap')])
        meta_yaml = open('meta.yml', 'w')
        meta_yaml.write('file_order:\n')
        tap_tar = tarfile.open(self.resultdir + '/tap.tar.gz', 'w:gz')
        for f in tap_files:
            meta_yaml.write("  - " + f.lstrip('./') + "\n")
            tap_tar.add(f)
        meta_yaml.close()
        tap_tar.add('meta.yml')
        tap_tar.close()


class base_job(object):
    """
    An abstract base class for the various autotest job classes.

    :property autodir: The top level autotest directory.
    :property clientdir: The autotest client directory.
    :property serverdir: The autotest server directory. [OPTIONAL]
    :property resultdir: The directory where results should be written out.
                         [WRITABLE]

    :property pkgdir: The job packages directory. [WRITABLE]
    :property tmpdir: The job temporary directory. [WRITABLE]
    :property testdir: The job test directory. [WRITABLE]
    :property customtestdir: The custom test directory. [WRITABLE]
    :property site_testdir: The job site test directory. [WRITABLE]

    :property bindir: The client bin/ directory.
    :property configdir: The client config/ directory.
    :property profdir: The client profilers/ directory.
    :property toolsdir: The client tools/ directory.

    :property conmuxdir: The conmux directory. [OPTIONAL]

    :property control: A path to the control file to be executed. [OPTIONAL]
    :property hosts: A set of all live Host objects currently in use by the
                     job. Code running in the context of a local client can
                     safely assume that this set contains only a single entry.
    :property machines: A list of the machine names associated with the job.
    :property user: The user executing the job.
    :property tag: A tag identifying the job. Often used by the scheduler to
                   give a name of the form NUMBER-USERNAME/HOSTNAME.
    :property args: A list of additional miscellaneous command-line arguments
                    provided when starting the job.

    :property last_boot_tag: The label of the kernel from the last reboot.
                             [OPTIONAL,PERSISTENT]
    :property automatic_test_tag: A string which, if set, will be automatically
                                  added to the test name when running tests.

    :property default_profile_only: A boolean indicating the default value of
                                    profile_only used by test.execute.
                                    [PERSISTENT]
    :property drop_caches: A boolean indicating if caches should be dropped
                           before each test is executed.
    :property drop_caches_between_iterations: A boolean indicating if caches
                                              should be dropped before each
                                              test iteration is executed.
    :property run_test_cleanup: A boolean indicating if test.cleanup should be
                                run by default after a test completes, if the
                                run_cleanup argument is not specified.
                                [PERSISTENT]

    :property num_tests_run: The number of tests run during the job. [OPTIONAL]
    :property num_tests_failed: The number of tests failed during the job.
                                [OPTIONAL]

    :property bootloader: An instance of the boottool class. May not be
                          available on job instances where access to the
                          bootloader is not available (e.g. on the server
                          running a server job). [OPTIONAL]
    :property harness: An instance of the client test harness. Only available
                       in contexts where client test execution happens.
                       [OPTIONAL]
    :property logging: An instance of the logging manager associated with the
                       job.
    :property profilers: An instance of the profiler manager associated with
                         the job.
    :property sysinfo: An instance of the sysinfo object. Only available in
                       contexts where it's possible to collect sysinfo.
    :property warning_manager: A class for managing which types of WARN
                               messages should be logged and which should be
                               suppressed. [OPTIONAL]
    :property warning_loggers: A set of readable streams that will be monitored
                               for WARN messages to be logged. [OPTIONAL]

    Abstract methods:
        _find_base_directories [CLASSMETHOD]
            Returns the location of autodir, clientdir and serverdir

        _find_resultdir
            Returns the location of resultdir. Gets a copy of any parameters
            passed into base_job.__init__. Can return None to indicate that
            no resultdir is to be used.

        _get_status_logger
            Returns a status_logger instance for recording job status logs.
    """

    # capture the dependency on several helper classes with factories
    _job_directory = job_directory
    _job_state = job_state

    # all the job directory attributes
    autodir = _job_directory.property_factory('autodir')
    clientdir = _job_directory.property_factory('clientdir')
    serverdir = _job_directory.property_factory('serverdir')
    resultdir = _job_directory.property_factory('resultdir')
    pkgdir = _job_directory.property_factory('pkgdir')
    tmpdir = _job_directory.property_factory('tmpdir')
    testdir = _job_directory.property_factory('testdir')
    customtestdir = _job_directory.property_factory('customtestdir')
    site_testdir = _job_directory.property_factory('site_testdir')
    bindir = _job_directory.property_factory('bindir')
    configdir = _job_directory.property_factory('configdir')
    profdir = _job_directory.property_factory('profdir')
    toolsdir = _job_directory.property_factory('toolsdir')
    conmuxdir = _job_directory.property_factory('conmuxdir')

    # all the generic persistent properties
    tag = _job_state.property_factory('_state', 'tag', '')
    default_profile_only = _job_state.property_factory(
        '_state', 'default_profile_only', False)
    run_test_cleanup = _job_state.property_factory(
        '_state', 'run_test_cleanup', True)
    last_boot_tag = _job_state.property_factory(
        '_state', 'last_boot_tag', None)
    automatic_test_tag = _job_state.property_factory(
        '_state', 'automatic_test_tag', None)

    # the use_sequence_number property
    _sequence_number = _job_state.property_factory(
        '_state', '_sequence_number', None)

    def _get_use_sequence_number(self):
        return bool(self._sequence_number)

    def _set_use_sequence_number(self, value):
        if value:
            self._sequence_number = 1
        else:
            self._sequence_number = None

    use_sequence_number = property(_get_use_sequence_number,
                                   _set_use_sequence_number)

    def __init__(self, *args, **dargs):
        # initialize the base directories, all others are relative to these
        autodir, clientdir, serverdir = self._find_base_directories()
        self._autodir = self._job_directory(autodir)
        self._clientdir = self._job_directory(clientdir)
        if serverdir:
            self._serverdir = self._job_directory(serverdir)
        else:
            self._serverdir = None

        # initialize all the other directories relative to the base ones
        self._initialize_dir_properties()
        self._resultdir = self._job_directory(
            self._find_resultdir(*args, **dargs), True)
        self._execution_contexts = []

        # initialize all the job state
        self._state = self._job_state()

        # initialize tap reporting
        if 'options' in dargs:
            self._tap = self._tap_init(dargs['options'].tap_report)
        else:
            self._tap = self._tap_init(False)

    @classmethod
    # The unittests will hide this method, well, for unittesting
    # pylint: disable=E0202
    def _find_base_directories(cls):
        raise NotImplementedError()

    def _initialize_dir_properties(self):
        """
        Initializes all the secondary self.*dir properties. Requires autodir,
        clientdir and serverdir to already be initialized.
        """

        # create some stubs for use as shortcuts
        def readonly_dir(*args):
            return self._job_directory(os.path.join(*args))

        def readwrite_dir(*args):
            return self._job_directory(os.path.join(*args), True)

        # various client-specific directories
        self._bindir = readonly_dir(self.clientdir)
        self._configdir = readonly_dir(self.clientdir, 'config')
        self._profdir = readonly_dir(self.clientdir, 'profilers')
        self._toolsdir = readonly_dir(self.clientdir, 'tools')

        try:
            autodir = os.path.abspath(os.environ['AUTODIR'])
        except KeyError:
            autodir = settings.get_value('COMMON', 'autotest_top_path')

        tmpdir = os.path.join(autodir, 'tmp')

        test_out_dir = settings.get_value('COMMON', 'test_output_dir',
                                          default=tmpdir)

        if self.serverdir:
            root = self.serverdir
        else:
            root = self.clientdir

        test_dir = settings.get_value('COMMON', 'test_dir',
                                      default=os.path.join(root, 'tests'))

        self._tmpdir = readwrite_dir(test_out_dir, 'tmp')

        # special case packages for backwards compatibility
        pkg_dir = test_out_dir
        if pkg_dir == self.serverdir:
            pkg_dir = self.clientdir
        self._pkgdir = readwrite_dir(pkg_dir, 'packages')

        # Now tests are read-only modules
        self._testdir = readonly_dir(test_dir)
        if 'CUSTOM_DIR' in os.environ:
            self._customtestdir = readonly_dir(os.environ['CUSTOM_DIR'])
        else:
            self._customtestdir = readonly_dir(test_dir)
        self._site_testdir = readwrite_dir(test_out_dir, 'site_tests')

        # various server-specific directories
        if self.serverdir:
            # This is a NOT a flexible solution, but I feel that this does
            # not deserve a configuration option by itself. So, let's just
            # try to find conmux in the system and let the user know about it
            if os.path.isdir('/usr/share/conmux'):
                self._conmuxdir = readonly_dir('/usr/share/conmux')
            else:
                self._conmuxdir = readonly_dir(self.autodir, 'conmux')
            logging.info('conmux directory set to: %s' % self._conmuxdir)
        else:
            self._conmuxdir = None

    # The unittests will hide this method, well, for unittesting
    # pylint: disable=E0202
    def _find_resultdir(self, *args, **dargs):
        raise NotImplementedError()

    def push_execution_context(self, resultdir):
        """
        Save off the current context of the job and change to the given one.

        In practice method just changes the resultdir, but it may become more
        extensive in the future. The expected use case is for when a child
        job needs to be executed in some sort of nested context (for example
        the way parallel_simple does). The original context can be restored
        with a pop_execution_context call.

        :param resultdir: The new resultdir, relative to the current one.
        """
        new_dir = self._job_directory(
            os.path.join(self.resultdir, resultdir), True)
        self._execution_contexts.append(self._resultdir)
        self._resultdir = new_dir

    def pop_execution_context(self):
        """
        Reverse the effects of the previous push_execution_context call.

        :raises: :class:`IndexError` when the stack of contexts is empty.
        """
        if not self._execution_contexts:
            raise IndexError('No old execution context to restore')
        self._resultdir = self._execution_contexts.pop()

    def get_state(self, name, default=_job_state.NO_DEFAULT):
        """
        Returns the value associated with a particular name.

        :param name: The name the value was saved with.
        :param default: A default value to return if no state is currently
            associated with var.

        :returns: A deep copy of the value associated with name. Note that this
                  explicitly returns a deep copy to avoid problems with mutable
                  values; mutations are not persisted or shared.
        :raises: :class:`KeyError` when no state is associated with var and a
                 default value is not provided.
        """
        try:
            return self._state.get('public', name, default=default)
        except KeyError:
            raise KeyError(name)

    def set_state(self, name, value):
        """
        Saves the value given with the provided name.

        :param name: The name the value should be saved with.
        :param value: The value to save.
        """
        self._state.set('public', name, value)

    def _build_tagged_test_name(self, testname, dargs):
        """
        Builds the fully tagged testname and subdirectory for job.run_test.

        :param testname: The base name of the test
        :param dargs: The ** arguments passed to run_test. And arguments
                      consumed by this method will be removed from the
                      dictionary.

        :returns: A 3-tuple of the full name of the test, the subdirectory it
                  should be stored in, and the full tag of the subdir.
        """
        tag_parts = []

        # build up the parts of the tag used for the test name
        master_testpath = dargs.get('master_testpath', "")
        base_tag = dargs.pop('tag', None)
        if base_tag:
            tag_parts.append(str(base_tag))
        if self.use_sequence_number:
            tag_parts.append('_%02d_' % self._sequence_number)
            self._sequence_number += 1
        if self.automatic_test_tag:
            tag_parts.append(self.automatic_test_tag)
        full_testname = '.'.join([testname] + tag_parts)

        # build up the subdir and tag as well
        subdir_tag = dargs.pop('subdir_tag', None)
        if subdir_tag:
            tag_parts.append(subdir_tag)
        subdir = '.'.join([testname] + tag_parts)
        subdir = os.path.join(master_testpath, subdir)
        tag = '.'.join(tag_parts)

        return full_testname, subdir, tag

    def _make_test_outputdir(self, subdir):
        """
        Creates an output directory for a test to run it.

        :param subdir: The subdirectory of the test. Generally computed by
                       _build_tagged_test_name.

        :returns: A job_directory instance corresponding to the outputdir of
                  the test.
        :raises: class:`TestError` If the output directory is invalid.
        """
        # explicitly check that this subdirectory is new
        path = os.path.join(self.resultdir, subdir)
        if os.path.exists(path):
            msg = ('%s already exists; multiple tests cannot run with the '
                   'same subdirectory' % subdir)
            raise error.TestError(msg)

        # create the outputdir and raise a TestError if it isn't valid
        try:
            outputdir = self._job_directory(path, True)
            return outputdir
        except self._job_directory.JobDirectoryException, e:
            logging.exception('%s directory creation failed with %s',
                              subdir, e)
            raise error.TestError('%s directory creation failed' % subdir)

    def _tap_init(self, enable):
        """
        Initialize TAP reporting
        """
        return TAPReport(enable, resultdir=self.resultdir)

    def record(self, status_code, subdir, operation, status='',
               optional_fields=None):
        """
        Record a job-level status event.

        Logs an event noteworthy to the Autotest job as a whole. Messages will
        be written into a global status log file, as well as a subdir-local
        status log file (if subdir is specified).

        :param status_code: A string status code describing the type of status
                            entry being recorded. It must pass
                            log.is_valid_status to be considered valid.
        :param subdir: A specific results subdirectory this also applies to, or
                       None. If not None the subdirectory must exist.
        :param operation: A string describing the operation that was run.
        :param status: An optional human-readable message describing the status
                       entry, for example an error message or "completed
                       successfully".
        :param optional_fields: An optional dictionary of additional named
                                fields to be included with the status message.
                                Every time timestamp and localtime entries are
                                generated with the current time and added to
                                this dictionary.
        """
        entry = status_log_entry(status_code, subdir, operation, status,
                                 optional_fields)
        self.record_entry(entry)

    def record_entry(self, entry, log_in_subdir=True):
        """
        Record a job-level status event, using a status_log_entry.

        This is the same as self.record but using an existing status log
        entry object rather than constructing one for you.

        :param entry: A status_log_entry object
        :param log_in_subdir: A boolean that indicates (when true) that subdir
                              logs should be written into the subdirectory
                              status log file.
        """
        self._get_status_logger().record_entry(entry, log_in_subdir)
