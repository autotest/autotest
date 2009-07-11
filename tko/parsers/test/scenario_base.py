"""Base support for parser scenario testing.
"""

from os import path
import ConfigParser, os, shelve, shutil, sys, tarfile, time
import difflib, itertools
import common
from autotest_lib.client.common_lib import utils, autotemp
from autotest_lib.tko import status_lib
from autotest_lib.tko.parsers.test import templates
from autotest_lib.tko.parsers.test import unittest_hotfix

TEMPLATES_DIRPATH = templates.__path__[0]
# Set TZ used to UTC
os.environ['TZ'] = 'UTC'
time.tzset()

KEYVAL = 'keyval'
STATUS_VERSION = 'status_version'
PARSER_RESULT_STORE = 'parser_result.store'
RESULTS_DIR_TARBALL = 'results_dir.tgz'
CONFIG_FILENAME = 'scenario.cfg'
TEST = 'test'
PARSER_RESULT_TAG = 'parser_result_tag'


class Error(Exception):
    pass


class BadResultsDirectoryError(Error):
    pass


class UnsupportedParserResultError(Error):
    pass


class UnsupportedTemplateTypeError(Error):
    pass



class ParserException(object):
    """Abstract representation of exception raised from parser execution.

    We will want to persist exceptions raised from the parser but also change
    the objects that make them up during refactor. For this reason
    we can't merely pickle the original.
    """

    def __init__(self, orig):
        """
        Args:
          orig: Exception; To copy
        """
        self.classname = orig.__class__.__name__
        print "Copying exception:", self.classname
        for key, val in orig.__dict__.iteritems():
            setattr(self, key, val)


    def __eq__(self, other):
        """Test if equal to another ParserException."""
        return self.__dict__ == other.__dict__


    def __ne__(self, other):
        """Test if not equal to another ParserException."""
        return self.__dict__ != other.__dict__


    def __str__(self):
        sd = self.__dict__
        pairs = ['%s="%s"' % (k, sd[k]) for k in sorted(sd.keys())]
        return "<%s: %s>" % (self.classname, ', '.join(pairs))


class ParserTestResult(object):
    """Abstract representation of test result parser state.

    We will want to persist test results but also change the
    objects that make them up during refactor. For this reason
    we can't merely pickle the originals.
    """

    def __init__(self, orig):
        """
        Tracking all the attributes as they change over time is
        not desirable. Instead we populate the instance's __dict__
        by introspecting orig.

        Args:
            orig: testobj; Framework test result instance to copy.
        """
        for key, val in orig.__dict__.iteritems():
            if key == 'kernel':
                setattr(self, key, dict(val.__dict__))
            elif key == 'iterations':
                setattr(self, key, [dict(it.__dict__) for it in val])
            else:
                setattr(self, key, val)


    def __eq__(self, other):
        """Test if equal to another ParserTestResult."""
        return self.__dict__ == other.__dict__


    def __ne__(self, other):
        """Test if not equal to another ParserTestResult."""
        return self.__dict__ != other.__dict__


    def __str__(self):
        sd = self.__dict__
        pairs = ['%s="%s"' % (k, sd[k]) for k in sorted(sd.keys())]
        return "<%s: %s>" % (self.__class__.__name__, ', '.join(pairs))


def copy_parser_result(parser_result):
    """Copy parser_result into ParserTestResult instances.

    Args:
      parser_result:
          list; [testobj, ...]
          - Or -
          Exception

    Returns:
      list; [ParserTestResult, ...]
      - Or -
      ParserException

    Raises:
        UnsupportedParserResultError; If parser_result type is not supported
    """
    if type(parser_result) is list:
        return [ParserTestResult(test) for test in parser_result]
    elif isinstance(parser_result, Exception):
        return ParserException(parser_result)
    else:
        raise UnsupportedParserResultError


def compare_parser_results(left, right):
    """Generates a textual report (for now) on the differences between.

    Args:
      left: list of ParserTestResults or a single ParserException
      right: list of ParserTestResults or a single ParserException

    Returns: Generator returned from difflib.Differ().compare()
    """
    def to_los(obj):
        """Generate a list of strings representation of object."""
        if type(obj) is list:
            return [
                '%d) %s' % pair
                for pair in itertools.izip(itertools.count(), obj)]
        else:
            return ['i) %s' % obj]

    return difflib.Differ().compare(to_los(left), to_los(right))


class ParserHarness(object):
    """Harness for objects related to the parser.

    This can exercise a parser on specific result data in various ways.
    """

    def __init__(
        self, parser, job, job_keyval, status_version, status_log_filepath):
        """
        Args:
          parser: tko.parsers.base.parser; Subclass instance of base parser.
          job: job implementation; Returned from parser.make_job()
          job_keyval: dict; Result of parsing job keyval file.
          status_version: str; Status log format version
          status_log_filepath: str; Path to result data status.log file
        """
        self.parser = parser
        self.job = job
        self.job_keyval = job_keyval
        self.status_version = status_version
        self.status_log_filepath = status_log_filepath


    def execute(self):
        """Basic exercise, pass entire log data into .end()

        Returns: list; [testobj, ...]
        """
        status_lines = open(self.status_log_filepath).readlines()
        self.parser.start(self.job)
        return self.parser.end(status_lines)


class BaseScenarioTestCase(unittest_hotfix.TestCase):
    """Base class for all Scenario TestCase implementations.

    This will load up all resources from scenario package directory upon
    instantiation, and initialize a new ParserHarness before each test
    method execution.
    """
    def __init__(self, methodName='runTest'):
        unittest_hotfix.TestCase.__init__(self, methodName)
        self.package_dirpath = path.dirname(
            sys.modules[self.__module__].__file__)
        self.tmp_dirpath, self.results_dirpath = load_results_dir(
            self.package_dirpath)
        self.parser_result_store = load_parser_result_store(
            self.package_dirpath)
        self.config = load_config(self.package_dirpath)
        self.parser_result_tag = self.config.get(
            TEST, PARSER_RESULT_TAG)
        self.expected_status_version = self.config.getint(
            TEST, STATUS_VERSION)
        self.harness = None


    def setUp(self):
        if self.results_dirpath:
            self.harness = new_parser_harness(self.results_dirpath)


    def tearDown(self):
        if self.tmp_dirpath:
            self.tmp_dirpath.clean()


    def test_status_version(self):
        """Ensure basic sanity."""
        self.skipIf(not self.harness)
        self.assertEquals(
            self.harness.status_version, self.expected_status_version)


def shelve_open(filename, flag='c', protocol=None, writeback=False):
    """A more system-portable wrapper around shelve.open, with the exact
    same arguments and interpretation."""
    import dumbdbm
    return shelve.Shelf(dumbdbm.open(filename, flag), protocol, writeback)


def new_parser_harness(results_dirpath):
    """Ensure sane environment and create new parser with wrapper.

    Args:
      results_dirpath: str; Path to job results directory

    Returns:
      ParserHarness;

    Raises:
      BadResultsDirectoryError; If results dir does not exist or is malformed.
    """
    if not path.exists(results_dirpath):
        raise BadResultsDirectoryError

    keyval_path = path.join(results_dirpath, KEYVAL)
    job_keyval = utils.read_keyval(keyval_path)
    status_version = job_keyval[STATUS_VERSION]
    parser = status_lib.parser(status_version)
    job = parser.make_job(results_dirpath)
    status_log_filepath = path.join(results_dirpath, 'status.log')
    if not path.exists(status_log_filepath):
        raise BadResultsDirectoryError

    return ParserHarness(
        parser, job, job_keyval, status_version, status_log_filepath)


def store_parser_result(package_dirpath, parser_result, tag):
    """Persist parser result to specified scenario package, keyed by tag.

    Args:
      package_dirpath: str; Path to scenario package directory.
      parser_result: list or Exception; Result from ParserHarness.execute
      tag: str; Tag to use as shelve key for persisted parser_result
    """
    copy = copy_parser_result(parser_result)
    sto_filepath = path.join(package_dirpath, PARSER_RESULT_STORE)
    sto = shelve_open(sto_filepath)
    sto[tag] = copy
    sto.close()


def load_parser_result_store(package_dirpath, open_for_write=False):
    """Load parser result store from specified scenario package.

    Args:
      package_dirpath: str; Path to scenario package directory.
      open_for_write: bool; Open store for writing.

    Returns:
      shelve.DbfilenameShelf; Looks and acts like a dict
    """
    open_flag = open_for_write and 'c' or 'r'
    sto_filepath = path.join(package_dirpath, PARSER_RESULT_STORE)
    return shelve_open(sto_filepath, flag=open_flag)


def store_results_dir(package_dirpath, results_dirpath):
    """Make tarball of results_dirpath in package_dirpath.

    Args:
      package_dirpath: str; Path to scenario package directory.
      results_dirpath: str; Path to job results directory
    """
    tgz_filepath = path.join(package_dirpath, RESULTS_DIR_TARBALL)
    tgz = tarfile.open(tgz_filepath, 'w:gz')
    results_dirname = path.basename(results_dirpath)
    tgz.add(results_dirpath, results_dirname)
    tgz.close()


def load_results_dir(package_dirpath):
    """Unpack results tarball in package_dirpath to temp dir.

    Args:
      package_dirpath: str; Path to scenario package directory.

    Returns:
      str; New temp path for extracted results directory.
      - Or -
      None; If tarball does not exist
    """
    tgz_filepath = path.join(package_dirpath, RESULTS_DIR_TARBALL)
    if not path.exists(tgz_filepath):
        return None, None

    tgz = tarfile.open(tgz_filepath, 'r:gz')
    tmp_dirpath = autotemp.tempdir(unique_id='scenario_base')
    results_dirname = tgz.next().name
    tgz.extract(results_dirname, tmp_dirpath.name)
    for info in tgz:
        tgz.extract(info.name, tmp_dirpath.name)
    return tmp_dirpath, path.join(tmp_dirpath.name, results_dirname)


def write_config(package_dirpath, **properties):
    """Write test configuration file to package_dirpath.

    Args:
      package_dirpath: str; Path to scenario package directory.
      properties: dict; Key value entries to write to to config file.
    """
    config = ConfigParser.RawConfigParser()
    config.add_section(TEST)
    for key, val in properties.iteritems():
        config.set(TEST, key, val)

    config_filepath = path.join(package_dirpath, CONFIG_FILENAME)
    fi = open(config_filepath, 'w')
    config.write(fi)
    fi.close()


def load_config(package_dirpath):
    """Load config from package_dirpath.

    Args:
      package_dirpath: str; Path to scenario package directory.

    Returns:
      ConfigParser.RawConfigParser;
    """
    config = ConfigParser.RawConfigParser()
    config_filepath = path.join(package_dirpath, CONFIG_FILENAME)
    config.read(config_filepath)
    return config


def install_unittest_module(package_dirpath, template_type):
    """Install specified unittest template module to package_dirpath.

    Template modules are stored in tko/parsers/test/templates.
    Installation includes:
      Copying to package_dirpath/template_type_unittest.py
      Copying scenario package common.py to package_dirpath
      Touching package_dirpath/__init__.py

    Args:
      package_dirpath: str; Path to scenario package directory.
      template_type: str; Name of template module to install.

    Raises:
      UnsupportedTemplateTypeError; If there is no module in
          templates package called template_type.
    """
    from_filepath = path.join(
        TEMPLATES_DIRPATH, '%s.py' % template_type)
    if not path.exists(from_filepath):
        raise UnsupportedTemplateTypeError

    to_filepath = path.join(
        package_dirpath, '%s_unittest.py' % template_type)
    shutil.copy(from_filepath, to_filepath)

    # For convenience we must copy the common.py hack file too :-(
    from_common_filepath = path.join(
        TEMPLATES_DIRPATH, 'scenario_package_common.py')
    to_common_filepath = path.join(package_dirpath, 'common.py')
    shutil.copy(from_common_filepath, to_common_filepath)

    # And last but not least, touch an __init__ file
    os.mknod(path.join(package_dirpath, '__init__.py'))


def fix_package_dirname(package_dirname):
    """Convert package_dirname to a valid package name string, if necessary.

    Args:
      package_dirname: str; Name of scenario package directory.

    Returns:
      str; Possibly fixed package_dirname
    """
    # Really stupid atm, just enough to handle results dirnames
    package_dirname = package_dirname.replace('-', '_')
    pre = ''
    if package_dirname[0].isdigit():
        pre = 'p'
    return pre + package_dirname


def sanitize_results_data(results_dirpath):
    """Replace or remove any data that would possibly contain IP

    Args:
      results_dirpath: str; Path to job results directory
    """
    raise NotImplementedError
