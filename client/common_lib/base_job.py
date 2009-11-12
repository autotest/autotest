import os

from autotest_lib.client.common_lib import autotemp, error


class job_directory(object):
    """Represents a job.*dir directory."""


    class MissingDirectoryException(error.AutotestError):
        """Raised when a directory required by the job does not exist."""
        def __init__(self, path):
            Exception.__init__(self, 'Directory %s does not exist' % path)


    class UncreatableDirectoryException(error.AutotestError):
        """Raised when a directory required by the job is missing and cannot
        be created."""
        def __init__(self, path, error):
            msg = 'Creation of directory %s failed with exception %s'
            msg %= (path, error)
            Exception.__init__(self, msg)


    class UnwritableDirectoryException(error.AutotestError):
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
        # check to ensure that the directory exists
        if not os.path.isdir(self.path):
            if is_writable:
                try:
                    os.makedirs(self.path)
                except OSError, e:
                    raise self.UncreatableDirectoryException(self.path, e)
            else:
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
        machines
            A list of the machine names associated with the job.
        user
            The user executing the job.
        tag
            A tag identifying the job. Often used by the scheduler to give
            a name of the form NUMBER-USERNAME/HOSTNAME. [OPTIONAL]

        last_boot_tag
            The label of the kernel from the last reboot. [OPTIONAL]
        default_profile_only
            A boolean indicating the default value of profile_only used
            by test.execute.
        drop_caches
            A boolean indicating if caches should be dropped before each
            test is executed.
        drop_caches_between_iterations
            A boolean indicating if caches should be dropped before each
            test iteration is executed.

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

    # all the job directory attributes
    autodir = job_directory.property_factory('autodir')
    clientdir = job_directory.property_factory('clientdir')
    serverdir = job_directory.property_factory('serverdir')
    resultdir = job_directory.property_factory('resultdir')
    pkgdir = job_directory.property_factory('pkgdir')
    tmpdir = job_directory.property_factory('tmpdir')
    testdir = job_directory.property_factory('testdir')
    site_testdir = job_directory.property_factory('site_testdir')
    bindir = job_directory.property_factory('bindir')
    configdir = job_directory.property_factory('configdir')
    profdir = job_directory.property_factory('profdir')
    toolsdir = job_directory.property_factory('toolsdir')
    conmuxdir = job_directory.property_factory('conmuxdir')


    # capture the dependency of job_directory with a factory method
    _job_directory = job_directory


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
