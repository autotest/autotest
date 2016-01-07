import os

try:
    import autotest.common as common  # pylint: disable=W0611
except ImportError:
    import common  # pylint: disable=W0611

# High level way of installing each autotest component
import client.setup
import shared.setup
import frontend.setup
import cli.setup
import server.setup
import scheduler.setup
import database_legacy.setup
import tko.setup
import utils.setup
import mirror.setup
import installation_support.setup

# pylint: disable=E0611
from distutils.core import setup

try:
    from sphinx.setup_command import BuildDoc
    cmdclass = {'build_doc': BuildDoc}
    command_options = {'build_doc': {'source_dir':
                                     ('setup.py', 'documentation/source')}}
except ImportError:
    cmdclass = {}
    command_options = {}

from autotest.client.shared import version


def _combine_dicts(list_dicts):
    result_dict = {}
    for d in list_dicts:
        for k in d:
            result_dict[k] = d[k]
    return result_dict


def _fix_data_paths(package_data_dict):
    '''
    Corrects package data paths

    When the package name is compound, and the package contents, that
    is, file paths, contain the same path name found in the package
    name, setuptools thinks there's an extra directory. This checks
    that condition and adjusts (strips) the 1st directory name.
    '''
    result = {}
    for package_name, package_content in package_data_dict.items():
        package_structure = package_name.split('.')
        package_structure_1st_level = package_structure[1]

        result[package_name] = []
        for p in package_content:
            path_structure = p.split(os.path.sep)
            path_structure_1st_level = path_structure[0]

            if package_structure_1st_level == path_structure_1st_level:
                path = os.path.join(*path_structure[1:])
            else:
                path = p

            result[package_name].append(path)

    return result


def get_package_dir():
    return _combine_dicts([client.setup.get_package_dir(),
                           shared.setup.get_package_dir(),
                           frontend.setup.get_package_dir(),
                           cli.setup.get_package_dir(),
                           server.setup.get_package_dir(),
                           scheduler.setup.get_package_dir(),
                           database_legacy.setup.get_package_dir(),
                           tko.setup.get_package_dir(),
                           utils.setup.get_package_dir(),
                           mirror.setup.get_package_dir()])


def get_packages():
    return (client.setup.get_packages() +
            shared.setup.get_packages() +
            frontend.setup.get_packages() +
            cli.setup.get_packages() +
            server.setup.get_packages() +
            scheduler.setup.get_packages() +
            database_legacy.setup.get_packages() +
            tko.setup.get_packages() +
            utils.setup.get_packages() +
            mirror.setup.get_packages() +
            installation_support.setup.get_packages())


def get_data_files():
    return (client.setup.get_data_files() +
            tko.setup.get_data_files() +
            utils.setup.get_data_files() +
            mirror.setup.get_data_files())


def get_package_data():
    return _combine_dicts([
        _fix_data_paths(client.setup.get_package_data()),
        _fix_data_paths(frontend.setup.get_package_data()),
        _fix_data_paths(cli.setup.get_package_data()),
        _fix_data_paths(server.setup.get_package_data()),
        _fix_data_paths(scheduler.setup.get_package_data()),
        _fix_data_paths(database_legacy.setup.get_package_data()),
        _fix_data_paths(utils.setup.get_package_data())
    ])


def get_scripts():
    return (client.setup.get_scripts() +
            frontend.setup.get_scripts() +
            cli.setup.get_scripts() +
            server.setup.get_scripts() +
            scheduler.setup.get_scripts() +
            database_legacy.setup.get_scripts() +
            tko.setup.get_scripts() +
            installation_support.setup.get_scripts())


def run():
    setup(name='autotest',
          description='Autotest test framework',
          maintainer='Lucas Meneghel Rodrigues',
          maintainer_email='lmr@redhat.com',
          version=version.get_version(),
          url='http://autotest.github.com',
          package_dir=get_package_dir(),
          package_data=get_package_data(),
          packages=get_packages(),
          scripts=get_scripts(),
          data_files=get_data_files(),
          cmdclass=cmdclass,
          command_options=command_options,
          )


if __name__ == '__main__':
    run()
