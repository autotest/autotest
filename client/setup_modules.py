"""
Module used to create the autotest namespace for single dir use case.

Autotest programs can be used and developed without requiring it to be
installed system-wide. In order for the code to see the library namespace:

from autotest.client.shared import error
from autotest.server import hosts
...

Without system wide install, we need some hacks, that are performed here.

:author: John Admanski (jadmanski@google.com)
"""
import os
import sys

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
import imp


def _create_module(name):
    """
    Create a single top-level module and add it to sys.modules.

    :param name: Module name, such as 'autotest'.
    """
    module = new.module(name)
    sys.modules[name] = module
    return module


def _create_module_and_parents(name):
    """
    Create a module, and all the necessary parents and add them to sys.modules.

    :param name: Module name, such as 'autotest.client'.
    """
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
    """
    Equivalent to 'from from_where import module'.

    :param module: Module name.
    :param from_where: Package from where the module is being imported.
    :return: The corresponding module.
    """
    from_module = __import__(from_where, globals(), locals(), [module])
    return getattr(from_module, module)


def setup(base_path, root_module_name="autotest"):
    """
    Setup a library namespace, with the appropriate top root module name.

    Perform all the necessary setup so that all the packages at
    'base_path' can be imported via "import root_module_name.package".

    :param base_path: Base path for the module.
    :param root_module_name: Top level name for the module.
    """
    if root_module_name in sys.modules:
        # already set up
        return

    _create_module_and_parents(root_module_name)
    imp.load_package(root_module_name, base_path)

    # Allow locally installed third party packages to be found.
    # This is primarily for the benefit of frontend and tko so that they
    # may use libraries other than those available as system packages.
    sys.path.insert(0, os.path.join(base_path, "site-packages"))
