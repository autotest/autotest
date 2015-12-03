# pylint: disable=E0611
import os
from distutils.core import setup

try:
    import autotest.common as common  # pylint: disable=W0611
except ImportError:
    import common  # pylint: disable=W0611

from autotest.client.shared import version

# Mostly needed when called one level up
if os.path.isdir('utils'):
    utils_dir = 'utils'
else:
    utils_dir = '.'

# TODO handle the init scripts


def get_package_dir():
    return {'autotest.utils': utils_dir}


def get_package_data():
    return {'autotest.utils': ['named_semaphore/*', 'modelviz/*']}


def get_packages():
    return ['autotest.utils']


def get_data_files():
    return [('share/autotest/utils', [utils_dir + '/autotestd.service',
                                      utils_dir + '/autotest.init',
                                      utils_dir + '/autotest-rh.init',
                                      utils_dir + '/release'])]


def run():
    setup(name='autotest',
          description='Autotest testing framework - utility scripts',
          maintainer='Lucas Meneghel Rodrigues',
          maintainer_email='lmr@redhat.com',
          version=version.get_version(),
          url='http://autotest.github.com',
          package_dir=get_package_dir(),
          package_data=get_package_data(),
          packages=get_packages(),
          data_files=get_data_files())


if __name__ == '__main__':
    run()
