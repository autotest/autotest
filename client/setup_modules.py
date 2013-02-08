__author__ = "jadmanski@google.com (John Admanski)"

import os, sys, imp

try:
    import autotest.client.shared.check_version as check_version
except ImportError:
    # This must run on Python versions less than 2.4.
    dirname = os.path.dirname(sys.modules[__name__].__file__)
    common_dir = os.path.abspath(os.path.join(dirname, "shared"))
    sys.path.insert(0, common_dir)
    import check_version
    sys.path.pop(0)

check_version.check_python_version()

import new


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


def import_module(module, from_where):
    """Equivalent to 'from from_where import module'
    Returns the corresponding module"""
    from_module = __import__(from_where, globals(), locals(), [module])
    return getattr(from_module, module)


def setup(base_path, root_module_name="autotest"):
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
    if sys.modules.has_key(root_module_name):
        # already set up
        return

    _create_module_and_parents(root_module_name)
    imp.load_package(root_module_name, base_path)

    # Allow locally installed third party packages to be found
    # before any that are installed on the system itself when not.
    # running as a client.
    # This is primarily for the benefit of frontend and tko so that they
    # may use libraries other than those available as system packages.
    sys.path.insert(0, os.path.join(base_path, "site-packages"))
