# High level way of installing each autotest component
import client.setup
import frontend.setup
import cli.setup
import server.setup
import scheduler.setup
import database_legacy.setup
import tko.setup
import utils.setup
import mirror.setup

from distutils.core import setup

try:
    import autotest.common as common
except ImportError:
    import common

from autotest.client.shared import version

def _combine_dicts(list_dicts):
    result_dict = {}
    for d in list_dicts:
        for k in d:
            result_dict[k] = d[k]
    return result_dict


def get_package_dir():
    return _combine_dicts([client.setup.get_package_dir(),
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
            frontend.setup.get_packages() +
            cli.setup.get_packages() +
            server.setup.get_packages() +
            scheduler.setup.get_packages() +
            database_legacy.setup.get_packages() +
            tko.setup.get_packages() +
            utils.setup.get_packages() +
            mirror.setup.get_packages())


def get_data_files():
    return (client.setup.get_data_files() +
            tko.setup.get_data_files() +
            utils.setup.get_data_files() +
            mirror.setup.get_data_files())


def get_package_data():
    return _combine_dicts([client.setup.get_package_data(),
                           frontend.setup.get_package_data(),
                           cli.setup.get_package_data(),
                           server.setup.get_package_data(),
                           scheduler.setup.get_package_data(),
                           database_legacy.setup.get_package_data(),
                           tko.setup.get_package_data(),
                           utils.setup.get_package_data()])


def get_scripts():
    return (client.setup.get_scripts() +
            frontend.setup.get_scripts() +
            cli.setup.get_scripts() +
            server.setup.get_scripts() +
            scheduler.setup.get_scripts() +
            database_legacy.setup.get_scripts() +
            tko.setup.get_scripts())


def run():
    setup(name='autotest',
          description='Autotest test framework',
          maintainer='Lucas Meneghel Rodrigues',
          maintainer_email='lmr@redhat.com',
          version=version.get_version(),
          url='http://autotest.github.com',
          package_dir=get_package_dir(),
          package_data=get_package_data(),
          packages= get_packages(),
          scripts=get_scripts(),
          data_files=get_data_files())


if __name__ == '__main__':
    run()
