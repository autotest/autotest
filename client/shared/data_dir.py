#!/usr/bin/python
"""
Library used to provide the appropriate data dir for virt test.
"""
import glob
import inspect
import os
import shutil
import sys
import tempfile

_ROOT_PATH = os.path.join(sys.modules[__name__].__file__, "..", "..")
ROOT_DIR = os.path.abspath(_ROOT_PATH)
BASE_BACKEND_DIR = os.path.join(ROOT_DIR, 'backends')
DATA_DIR = os.path.join(ROOT_DIR, 'shared', 'data')
DEPS_DIR = os.path.join(ROOT_DIR, 'shared', 'deps')
DOWNLOAD_DIR = os.path.join(ROOT_DIR, 'shared', 'downloads')
TEST_PROVIDERS_DIR = os.path.join(ROOT_DIR, 'test-providers.d')
TEST_PROVIDERS_DOWNLOAD_DIR = os.path.join(ROOT_DIR, 'test-providers.d',
                                           'downloads')
TMP_DIR = os.path.join(ROOT_DIR, 'tmp')
BACKING_DATA_DIR = None


class MissingDepsDirError(Exception):
    pass


class UnknownBackendError(Exception):

    def __init__(self, backend):
        self.backend = backend

    def __str__(self):
        return ("Virt Backend %s is not currently supported by virt-test. "
                "Check for typos and the list of supported backends" %
                self.backend)


class SubdirList(list):

    """
    List of all non-hidden subdirectories beneath basedir
    """

    def __in_filter__(self, item):
        if self.filterlist:
            for _filter in self.filterlist:
                if item.count(str(_filter)):
                    return True
            return False
        else:
            return False

    def __set_initset__(self):
        for dirpath, dirnames, filenames in os.walk(self.basedir):
            del filenames  # not used
            # Don't modify list while in use
            del_list = []
            for _dirname in dirnames:
                if _dirname.startswith('.') or self.__in_filter__(_dirname):
                    # Don't descend into filtered or hidden directories
                    del_list.append(_dirname)
                else:
                    self.initset.add(os.path.join(dirpath, _dirname))
            # Remove items in del_list from dirnames list
            for _dirname in del_list:
                del dirnames[dirnames.index(_dirname)]

    def __init__(self, basedir, filterlist=None):
        self.basedir = os.path.abspath(str(basedir))
        self.initset = set([self.basedir])  # enforce unique items
        self.filterlist = filterlist
        self.__set_initset__()
        super(SubdirList, self).__init__(self.initset)


class SubdirGlobList(SubdirList):

    """
    List of all files matching glob in all non-hidden basedir subdirectories
    """

    def __initset_to_globset__(self):
        globset = set()
        for dirname in self.initset:  # dirname is absolute
            pathname = os.path.join(dirname, self.globstr)
            for filepath in glob.glob(pathname):
                if not self.__in_filter__(filepath):
                    globset.add(filepath)
        self.initset = globset

    def __set_initset__(self):
        super(SubdirGlobList, self).__set_initset__()
        self.__initset_to_globset__()

    def __init__(self, basedir, globstr, filterlist=None):
        self.globstr = str(globstr)
        super(SubdirGlobList, self).__init__(basedir, filterlist)


def get_backing_data_dir():
    if os.path.islink(DATA_DIR):
        if os.path.isdir(DATA_DIR):
            return os.readlink(DATA_DIR)
        else:
            # Invalid symlink
            os.unlink(DATA_DIR)
    elif os.path.isdir(DATA_DIR):
        return DATA_DIR

    try:
        return os.environ['VIRT_TEST_DATA_DIR']
    except KeyError:
        pass

    data_dir = '/var/lib/virt_test'
    if os.path.isdir(data_dir):
        try:
            fd, path = tempfile.mkstemp(dir=data_dir)
            os.close(fd)
            os.unlink(path)
            return data_dir
        except OSError:
            pass
    else:
        try:
            os.makedirs(data_dir)
            return data_dir
        except OSError:
            pass

    data_dir = os.path.expanduser('~/virt_test')
    if not os.path.isdir(data_dir):
        os.makedirs(data_dir)
    return os.path.realpath(data_dir)


def set_backing_data_dir(backing_data_dir):
    backing_data_dir = os.path.expanduser(backing_data_dir)
    try:
        os.symlink(backing_data_dir, DATA_DIR)
    except OSError:
        pass  # Assume existing link is correct
    if not os.path.isdir(backing_data_dir):
        os.makedirs(backing_data_dir)


BACKING_DATA_DIR = get_backing_data_dir()
set_backing_data_dir(BACKING_DATA_DIR)


def get_root_dir():
    return ROOT_DIR


def get_data_dir():
    return DATA_DIR


def get_backend_dir(backend_type):
    if backend_type not in os.listdir(BASE_BACKEND_DIR):
        raise UnknownBackendError(backend_type)
    return os.path.join(BASE_BACKEND_DIR, backend_type)


def get_backend_cfg_path(backend_type, cfg_basename):
    return os.path.join(BASE_BACKEND_DIR, backend_type, 'cfg', cfg_basename)


def get_deps_dir():
    """
    For a given test provider, report the appropriate deps dir.

    The little inspect trick is used to avoid callers having to do
    sys.modules[] tricks themselves.
    """
    # Get the frame that called this function
    frame = inspect.stack()[1]
    # This is the module that called the function
    module = inspect.getmodule(frame[0])
    # With the module path, we can keep searching with a parent dir with 'deps'
    # in it, which should be the correct deps directory.
    p = os.path.dirname(module.__file__)
    nesting_limit = 10
    index = 0
    while 'deps' not in os.listdir(p):
        if '.git' in os.listdir(p):
            raise MissingDepsDirError("Could not find a deps dir for git "
                                      "repo %s" % p)
        if index >= nesting_limit:
            raise MissingDepsDirError("Could not find a deps dir after "
                                      "looking %s parent directories" %
                                      nesting_limit)
        p = os.path.dirname(p)
        index += 1

    return os.path.join(p, 'deps')


def get_tmp_dir():
    if not os.path.isdir(TMP_DIR):
        os.makedirs(TMP_DIR)
    return TMP_DIR


def get_download_dir():
    return DOWNLOAD_DIR


def get_test_providers_dir():
    """
    Return the base test providers dir (at the moment, test-providers.d).
    """
    if not os.path.isdir(TEST_PROVIDERS_DOWNLOAD_DIR):
        os.makedirs(TEST_PROVIDERS_DOWNLOAD_DIR)
    return TEST_PROVIDERS_DIR


def get_test_provider_dir(provider):
    """
    Return a specific test providers dir, inside the base dir.
    """
    provider_dir = os.path.join(TEST_PROVIDERS_DOWNLOAD_DIR, provider)
    if not provider_dir:
        os.makedirs(provider_dir)
    return provider_dir


def clean_tmp_files():
    if os.path.isdir(TMP_DIR):
        hidden_paths = glob.glob(os.path.join(TMP_DIR, ".??*"))
        paths = glob.glob(os.path.join(TMP_DIR, "*"))
        for path in paths + hidden_paths:
            shutil.rmtree(path, ignore_errors=True)


if __name__ == '__main__':
    print("root dir:         " + ROOT_DIR)
    print("tmp dir:          " + TMP_DIR)
    print("data dir:         " + DATA_DIR)
    print("deps dir:         " + DEPS_DIR)
    print("backing data dir: " + BACKING_DATA_DIR)
    print("test providers dir: " + TEST_PROVIDERS_DIR)
