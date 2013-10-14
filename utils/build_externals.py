#!/usr/bin/python
#
# Please keep this code python 2.4 compatible and stand alone.

"""
Fetch, build and install external Python library dependancies.

This fetches external python libraries, builds them using your host's
python and installs them under our own autotest/site-packages/ directory.

Usage?  Just run it.
    utils/build_externals.py
"""

import compileall
import logging
import os
import shutil
import sys
import tempfile
import time
import urllib2
import subprocess
import re
try:
    import autotest.common as common
except ImportError:
    import common
from autotest.client.shared import logging_config, logging_manager
from autotest.client.shared import utils
from autotest.utils import external_packages

# bring in site packages as well
utils.import_site_module(__file__, 'autotest.utils.site_external_packages')

# Where package source be fetched to relative to the top of the autotest tree.
PACKAGE_DIR = 'ExternalSource'

# Where packages will be installed to relative to the top of the autotest tree.
INSTALL_DIR = 'site-packages'

# Installs all packages, even if the system already has the version required
INSTALL_ALL = False


# Want to add more packages to fetch, build and install?  See the class
# definitions at the end of external_packages.py for examples of how to do it.


class BuildExternalsLoggingConfig(logging_config.LoggingConfig):

    def configure_logging(self, results_dir=None, verbose=False):
        super(BuildExternalsLoggingConfig, self).configure_logging(
            use_console=True,
            verbose=verbose)


def main():
    """
    Find all ExternalPackage classes defined in this file and ask them to
    fetch, build and install themselves.
    """
    logging_manager.configure_logging(BuildExternalsLoggingConfig(),
                                      verbose=True)
    os.umask(022)

    top_of_tree = external_packages.find_top_of_autotest_tree()
    package_dir = os.path.join(top_of_tree, PACKAGE_DIR)
    install_dir = os.path.join(top_of_tree, INSTALL_DIR)

    # Make sure the install_dir is in our python module search path
    # as well as the PYTHONPATH being used by all our setup.py
    # install subprocesses.
    if install_dir not in sys.path:
        sys.path.insert(0, install_dir)
    env_python_path_varname = 'PYTHONPATH'
    env_python_path = os.environ.get(env_python_path_varname, '')
    if install_dir + ':' not in env_python_path:
        os.environ[env_python_path_varname] = ':'.join([
            install_dir, env_python_path])

    fetched_packages, fetch_errors = fetch_necessary_packages(package_dir,
                                                              install_dir)
    install_errors = build_and_install_packages(fetched_packages, install_dir)

    # Byte compile the code after it has been installed in its final
    # location as .pyc files contain the path passed to compile_dir().
    # When printing exception tracebacks, python uses that path first to look
    # for the source code before checking the directory of the .pyc file.
    # Don't leave references to our temporary build dir in the files.
    logging.info('compiling .py files in %s to .pyc', install_dir)
    compileall.compile_dir(install_dir, quiet=True)

    # Some things install with whacky permissions, fix that.
    external_packages.system("chmod -R a+rX '%s'" % install_dir)

    errors = fetch_errors + install_errors
    for error_msg in errors:
        logging.error(error_msg)

    return len(errors)


def fetch_necessary_packages(dest_dir, install_dir):
    """
    Fetches all ExternalPackages into dest_dir.

    :param dest_dir: Directory the packages should be fetched into.
    :param install_dir: Directory where packages will later installed.

    :return: A tuple containing two lists:
             * A list of ExternalPackage instances that were fetched and
               need to be installed.
             * A list of error messages for any failed fetches.
    """
    names_to_check = sys.argv[1:]
    errors = []
    fetched_packages = []
    for package_class in external_packages.ExternalPackage.subclasses:
        package = package_class()
        if names_to_check and package.name.lower() not in names_to_check:
            continue
        if not package.is_needed(install_dir):
            logging.info('A new %s is not needed on this system.',
                         package.name)
            if INSTALL_ALL:
                logging.info('Installing anyways...')
            else:
                continue
        if not package.fetch(dest_dir):
            msg = 'Unable to download %s' % package.name
            logging.error(msg)
            errors.append(msg)
        else:
            fetched_packages.append(package)

    return fetched_packages, errors


def build_and_install_packages(packages, install_dir):
    """
    Builds and installs all packages into install_dir.

    :param packages - A list of already fetched ExternalPackage instances.
    :param install_dir - Directory the packages should be installed into.

    :return: A list of error messages for any installs that failed.
    """
    errors = []
    for package in packages:
        if not package.build_and_install(install_dir):
            msg = 'Unable to build and install %s' % package.name
            logging.error(msg)
            errors.append(msg)
    return errors


if __name__ == '__main__':
    sys.exit(main())
