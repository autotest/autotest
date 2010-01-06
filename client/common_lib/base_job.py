import os, copy, logging, errno, tempfile, cPickle as pickle, platform

from autotest_lib.client.common_lib import autotemp, error


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

        @param path The path of the directory. If None a temporary directory
            will be created instead.
        @param is_writable If True, expect the directory to be writable.

        @raises MissingDirectoryException raised if is_writable=False and the
            directory does not exist.
        @raises UnwritableDirectoryException raised if is_writable=True and
            the directory exists but is not writable.
        @raises UncreatableDirectoryException raised if is_writable=True, the
            directory does not exist and it cannot be created.
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

        @param dir_path A path where a directory should be located
        @param is_writable A boolean indicating that the directory should
            not only exist, but also be writable.

        @raises MissingDirectoryException raised if is_writable=False and the
            directory does not exist.
        @raises UnwritableDirectoryException raised if is_writable=True and
            the directory is not wrtiable.
        @raises UncreatableDirectoryException raised if is_writable=True, the
            directory does not exist and it cannot be created
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

        @param attribute A string with the name of the attribute this is
            exposed as. '_'+attribute must then be attribute that holds
            either None or a job_directory-like object.

        @returns A read-only property object that exposes a job_directory path
        """
        @property
        def dir_property(self):
            underlying_attribute = getattr(self, '_' + attribute)
            if underlying_attribute is None:
                return None
            else:
                return underlying_attribute.path
        return dir_property


class job_state(object):
    """A class for managing explicit job and user state, optionally persistent.

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


    def get(self, namespace, name, default=NO_DEFAULT):
        """Returns the value associated with a particular name.

        @param namespace The namespace that the property should be stored in.
        @param name The name the value was saved with.
        @param default A default value to return if no state is currently
            associated with var.

        @returns A deep copy of the value associated with name. Note that this
            explicitly returns a deep copy to avoid problems with mutable
            values; mutations are not persisted or shared.
        @raises KeyError raised when no state is associated with var and a
            default value is not provided.
        """
        if self.has(namespace, name):
            return copy.deepcopy(self._state[namespace][name])
        elif default is self.NO_DEFAULT:
            raise KeyError('No key %s in namespace %s' % (name, namespace))
        else:
            return default


    def read_from_file(self, file_path):
        """Read in any state from the file at file_path.

        Any state specified only in-memory will be preserved. Any state
        specified on-disk will be set in-memory, even if an in-memory
        setting already exists. In the special case that the file does
        not exist it is treated as empty and not a failure.
        """
        # if the file exists, pull out its contents
        if file_path:
            try:
                on_disk_state = pickle.load(open(file_path))
            except IOError, e:
                if e.errno == errno.ENOENT:
                    logging.info('Persistent state file %s does not exist',
                                 file_path)
                    return
                else:
                    raise
        else:
            return

        # merge the on-disk state with the in-memory state
        for namespace, namespace_dict in on_disk_state.iteritems():
            in_memory_namespace = self._state.setdefault(namespace, {})
            for name, value in namespace_dict.iteritems():
                if name in in_memory_namespace:
                    if in_memory_namespace[name] != value:
                        logging.info('Persistent value of %s.%s from %s '
                                     'overridding existing in-memory value',
                                     namespace, name, file_path)
                        in_memory_namespace[name] = value
                    else:
                        logging.debug('Value of %s.%s is unchanged, skipping'
                                      'import', namespace, name)
                else:
                    logging.debug('Importing %s.%s from state file %s',
                                  namespace, name, file_path)
                    in_memory_namespace[name] = value

        # flush the merged state out to disk
        self._write_to_backing_file()


    def write_to_file(self, file_path):
        """Write out the current state to the given path.

        @param file_path The path where the state should be written out to.
            Must be writable.
        """
        outfile = open(file_path, 'w')
        try:
            pickle.dump(self._state, outfile, self.PICKLE_PROTOCOL)
        finally:
            outfile.close()
        logging.debug('Persistent state flushed to %s', file_path)


    def _write_to_backing_file(self):
        """Flush the current state to the backing file."""
        if self._backing_file:
            self.write_to_file(self._backing_file)


    def set_backing_file(self, file_path):
        """Change the path used as the backing file for the persistent state.

        When a new backing file is specified if a file already exists then
        its contents will be added into the current state, with conflicts
        between the file and memory being resolved in favor of the file
        contents. The file will then be kept in sync with the (combined)
        in-memory state. The syncing can be disabled by setting this to None.

        @param file_path A path on the filesystem that can be read from and
            written to, or None to turn off the backing store.
        """
        self._backing_file = None
        self.read_from_file(file_path)
        self._backing_file = file_path
        self._write_to_backing_file()


    def set(self, namespace, name, value):
        """Saves the value given with the provided name.

        @param namespace The namespace that the property should be stored in.
        @param name The name the value should be saved with.
        @param value The value to save.
        """
        namespace_dict = self._state.setdefault(namespace, {})
        namespace_dict[name] = copy.deepcopy(value)
        self._write_to_backing_file()
        logging.debug('Persistent state %s.%s now set to %r', namespace,
                      name, value)


    def has(self, namespace, name):
        """Return a boolean indicating if namespace.name is defined.

        @param namespace The namespace to check for a definition.
        @param name The name to check for a definition.

        @returns True if the given name is defined in the given namespace and
            False otherwise.
        """
        return namespace in self._state and name in self._state[namespace]


    def discard(self, namespace, name):
        """If namespace.name is a defined value, deletes it.

        @param namespace The namespace that the property is stored in.
        @param name The name the value is saved with.
        """
        if self.has(namespace, name):
            del self._state[namespace][name]
            if len(self._state[namespace]) == 0:
                del self._state[namespace]
            self._write_to_backing_file()
            logging.debug('Persistent state %s.%s deleted', namespace, name)
        else:
            logging.debug(
                'Persistent state %s.%s not defined so nothing is discarded',
                namespace, name)


    def discard_namespace(self, namespace):
        """Delete all defined namespace.* names.

        @param namespace The namespace to be cleared.
        """
        if namespace in self._state:
            del self._state[namespace]
        self._write_to_backing_file()
        logging.debug('Persistent state %s.* deleted', namespace)


    @staticmethod
    def property_factory(state_attribute, property_attribute, default,
                         namespace='global_properties'):
        """
        Create a property object for an attribute using self.get and self.set.

        @param state_attribute A string with the name of the attribute on
            job that contains the job_state instance.
        @param property_attribute A string with the name of the attribute
            this property is exposed as.
        @param default A default value that should be used for this property
            if it is not set.
        @param namespace The namespace to store the attribute value in.

        @returns A read-write property object that performs self.get calls
            to read the value and self.set calls to set it.
        """
        def getter(job):
            state = getattr(job, state_attribute)
            return state.get(namespace, property_attribute, default)
        def setter(job, value):
            state = getattr(job, state_attribute)
            state.set(namespace, property_attribute, value)
        return property(getter, setter)


class base_job(object):
    """An abstract base class for the various autotest job classes.

    Properties:
        autodir
            The top level autotest directory.
        clientdir
            The autotest client directory.
        serverdir
            The autotest server directory. [OPTIONAL]
        resultdir
            The directory where results should be written out. If not specified
            then results should not be written anywhere. [WRITABLE]

        pkgdir
            The job packages directory. [WRITABLE]
        tmpdir
            The job temporary directory. [WRITABLE]
        testdir
            The job test directory. [WRITABLE]
        site_testdir
            The job site test directory. [WRITABLE]

        bindir
            The client bin/ directory.
        configdir
            The client config/ directory.
        profdir
            The client profilers/ directory.
        toolsdir
            The client tools/ directory.

        conmuxdir
            The conmux directory. [OPTIONAL]

        control
            A path to the control file to be executed. [OPTIONAL]
        hosts
            A set of all live Host objects currently in use by the job.
            Code running in the context of a local client can safely assume
            that this set contains only a single entry.
        machines
            A list of the machine names associated with the job.
        user
            The user executing the job.
        tag
            A tag identifying the job. Often used by the scheduler to give
            a name of the form NUMBER-USERNAME/HOSTNAME. [OPTIONAL]

        last_boot_tag
            The label of the kernel from the last reboot. [OPTIONAL,PERSISTENT]
        automatic_test_tag
            A string which, if set, will be automatically added to the test
            name when running tests.

        default_profile_only
            A boolean indicating the default value of profile_only used
            by test.execute. [PERSISTENT]
        drop_caches
            A boolean indicating if caches should be dropped before each
            test is executed.
        drop_caches_between_iterations
            A boolean indicating if caches should be dropped before each
            test iteration is executed.
        run_test_cleanup
            A boolean indicating if test.cleanup should be run by default
            after a test completes, if the run_cleanup argument is not
            specified. [PERSISTENT]

        num_tests_run
            The number of tests run during the job. [OPTIONAL]
        num_tests_failed
            The number of tests failed during the job. [OPTIONAL]

        bootloader
            An instance of the boottool class. May not be available on job
            instances where access to the bootloader is not available
            (e.g. on the server running a server job). [OPTIONAL]
        harness
            An instance of the client test harness. Only available in contexts
            where client test execution happens. [OPTIONAL]
        logging
            An instance of the logging manager associated with the job.
        profilers
            An instance of the profiler manager associated with the job.
        sysinfo
            An instance of the sysinfo object. Only available in contexts
            where it's possible to collect sysinfo.
        warning_manager
            A class for managing which types of WARN messages should be
            logged and which should be supressed. [OPTIONAL]
        warning_loggers
            A set of readable streams that will be monitored for WARN messages
            to be logged. [OPTIONAL]

    Abstract methods:
        _find_base_directories [CLASSMETHOD]
            Returns the location of autodir, clientdir and serverdir

        _find_resultdir
            Returns the location of resultdir. Gets a copy of any parameters
            passed into base_job.__init__. Can return None to indicate that
            no resultdir is to be used.
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
    site_testdir = _job_directory.property_factory('site_testdir')
    bindir = _job_directory.property_factory('bindir')
    configdir = _job_directory.property_factory('configdir')
    profdir = _job_directory.property_factory('profdir')
    toolsdir = _job_directory.property_factory('toolsdir')
    conmuxdir = _job_directory.property_factory('conmuxdir')


    # all the generic persistent properties
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


    @classmethod
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
        self._bindir = readonly_dir(self.clientdir, 'bin')
        self._configdir = readonly_dir(self.clientdir, 'config')
        self._profdir = readonly_dir(self.clientdir, 'profilers')
        self._pkgdir = readwrite_dir(self.clientdir, 'packages')
        self._toolsdir = readonly_dir(self.clientdir, 'tools')

        # directories which are in serverdir on a server, clientdir on a client
        if self.serverdir:
            root = self.serverdir
        else:
            root = self.clientdir
        self._tmpdir = readwrite_dir(root, 'tmp')
        self._testdir = readwrite_dir(root, 'tests')
        self._site_testdir = readwrite_dir(root, 'site_tests')

        # various server-specific directories
        if self.serverdir:
            self._conmuxdir = readonly_dir(self.autodir, 'conmux')
        else:
            self._conmuxdir = None


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

        @param resultdir The new resultdir, relative to the current one.
        """
        new_dir = self._job_directory(
            os.path.join(self.resultdir, resultdir), True)
        self._execution_contexts.append(self._resultdir)
        self._resultdir = new_dir


    def pop_execution_context(self):
        """
        Reverse the effects of the previous push_execution_context call.

        @raises IndexError raised when the stack of contexts is empty.
        """
        if not self._execution_contexts:
            raise IndexError('No old execution context to restore')
        self._resultdir = self._execution_contexts.pop()


    def get_state(self, name, default=_job_state.NO_DEFAULT):
        """Returns the value associated with a particular name.

        @param name The name the value was saved with.
        @param default A default value to return if no state is currently
            associated with var.

        @returns A deep copy of the value associated with name. Note that this
            explicitly returns a deep copy to avoid problems with mutable
            values; mutations are not persisted or shared.
        @raises KeyError raised when no state is associated with var and a
            default value is not provided.
        """
        try:
            return self._state.get('public', name, default=default)
        except KeyError:
            raise KeyError(name)


    def set_state(self, name, value):
        """Saves the value given with the provided name.

        @param name The name the value should be saved with.
        @param value The value to save.
        """
        self._state.set('public', name, value)


    def _build_tagged_test_name(self, testname, dargs):
        """Builds the fully tagged testname and subdirectory for job.run_test.

        @param testname The base name of the test
        @param dargs The ** arguments passed to run_test. And arguments
            consumed by this method will be removed from the dictionary.

        @returns A 3-tuple of the full name of the test, the subdirectory it
            should be stored in, and the full tag of the subdir.
        """
        tag_parts = []

        # build up the parts of the tag used for the test name
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
        tag = '.'.join(tag_parts)

        return full_testname, subdir, tag


    def _make_test_outputdir(self, subdir):
        """Creates an output directory for a test to run it.

        @param subdir The subdirectory of the test. Generally computed by
            _build_tagged_test_name.

        @returns A job_directory instance corresponding to the outputdir of
            the test.
        @raises A TestError if the output directory is invalid.
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
