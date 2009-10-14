__author__ = "jadmanski@google.com (John Admanski)"

import os, sys

# This must run on Python versions less than 2.4.
dirname = os.path.dirname(sys.modules[__name__].__file__)
common_dir = os.path.abspath(os.path.join(dirname, "common_lib"))
sys.path.insert(0, common_dir)
import check_version
sys.path.pop(0)
check_version.check_python_version()

import new, glob, traceback


def _create_module(name):
    """Create a single top-level module"""
    module = new.module(name)
    sys.modules[name] = module
    return module


def _create_module_and_parents(name):
    """Create a module, and all the necessary parents"""
    parts = name.split(".")
    # first create the top-level module
    parent = _create_module(parts[0])
    created_parts = [parts[0]]
    parts.pop(0)
    # now, create any remaining child modules
    while parts:
        child_name = parts.pop(0)
        module = new.module(child_name)
        setattr(parent, child_name, module)
        created_parts.append(child_name)
        sys.modules[".".join(created_parts)] = module
        parent = module


def _import_children_into_module(parent_module_name, path):
    """Import all the packages on a path into a parent module"""
    # find all the packages at 'path'
    names = []
    for filename in os.listdir(path):
        full_name = os.path.join(path, filename)
        if not os.path.isdir(full_name):
            continue   # skip files
        if "." in filename:
            continue   # if "." is in the name it's not a valid package name
        if not os.access(full_name, os.R_OK | os.X_OK):
            continue   # need read + exec access to make a dir importable
        if "__init__.py" in os.listdir(full_name):
            names.append(filename)
    # import all the packages and insert them into 'parent_module'
    sys.path.insert(0, path)
    for name in names:
        module = __import__(name)
        # add the package to the parent
        parent_module = sys.modules[parent_module_name]
        setattr(parent_module, name, module)
        full_name = parent_module_name + "." + name
        sys.modules[full_name] = module
    # restore the system path
    sys.path.pop(0)


def import_module(module, from_where):
    """Equivalent to 'from from_where import module'
    Returns the corresponding module"""
    from_module = __import__(from_where, globals(), locals(), [module])
    return getattr(from_module, module)


def _autotest_logging_handle_error(self, record):
    """Method to monkey patch into logging.Handler to replace handleError."""
    # The same as the default logging.Handler.handleError but also prints
    # out the original record causing the error so there is -some- idea
    # about which call caused the logging error.
    import logging
    if logging.raiseExceptions:
        # Avoid recursion as the below output can end up back in here when
        # something has *seriously* gone wrong in autotest.
        logging.raiseExceptions = 0
        sys.stderr.write('Exception occurred formatting message: '
                         '%r using args %r\n' % (record.msg, record.args))
        traceback.print_stack()
        sys.stderr.write('-' * 50 + '\n')
        traceback.print_exc()
        sys.stderr.write('Future logging formatting exceptions disabled.\n')


def _monkeypatch_logging_handle_error():
    # Hack out logging.py*
    logging_py = os.path.join(os.path.dirname(__file__), "common_lib",
                              "logging.py*")
    if glob.glob(logging_py):
        os.system("rm -f %s" % logging_py)

    # Monkey patch our own handleError into the logging module's StreamHandler.
    # A nicer way of doing this -might- be to have our own logging module define
    # an autotest Logger instance that added our own Handler subclass with this
    # handleError method in it.  But that would mean modifying tons of code.
    import logging
    assert callable(logging.Handler.handleError)
    logging.Handler.handleError = _autotest_logging_handle_error


def setup(base_path, root_module_name=""):
    """
    Perform all the necessary setup so that all the packages at
    'base_path' can be imported via "import root_module_name.package".
    If root_module_name is empty, then all the packages at base_path
    are inserted as top-level packages.

    Also, setup all the common.* aliases for modules in the common
    library.

    The setup must be different if you are running on an Autotest server
    or on a test machine that just has the client directories installed.
    """
    # Hack... Any better ideas?
    if (root_module_name == 'autotest_lib.client' and
        os.path.exists(os.path.join(os.path.dirname(__file__),
                                    '..', 'server'))):
        root_module_name = 'autotest_lib'
        base_path = os.path.abspath(os.path.join(base_path, '..'))

    _create_module_and_parents(root_module_name)
    _import_children_into_module(root_module_name, base_path)

    if root_module_name == 'autotest_lib':
        # Allow locally installed third party packages to be found
        # before any that are installed on the system itself when not.
        # running as a client.
        # This is primarily for the benefit of frontend and tko so that they
        # may use libraries other than those available as system packages.
        sys.path.insert(0, os.path.join(base_path, "site-packages"))

    _monkeypatch_logging_handle_error()
