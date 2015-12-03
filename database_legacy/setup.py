# pylint: disable=E0611
import os
from distutils.core import setup

try:
    import autotest.common as common  # pylint: disable=W0611
except ImportError:
    import common  # pylint: disable=W0611

from autotest.client.shared import version

# Mostly needed when called one level up
if os.path.isdir('database_legacy'):
    db_dir = 'database_legacy'
else:
    db_dir = '.'


def get_package_dir():
    return {'autotest.database_legacy': db_dir}


def get_package_data():
    return {'autotest.database_legacy': ['*.sql']}


def get_packages():
    return ['autotest.database_legacy']


def get_scripts():
    return [db_dir + '/autotest-upgrade-db']


def run():
    setup(name='autotest',
          description='Autotest test framework - results database module',
          maintainer='Lucas Meneghel Rodrigues',
          maintainer_email='lmr@redhat.com',
          version=version.get_version(),
          url='http://autotest.github.com',
          package_dir=get_package_dir(),
          package_data=get_package_data(),
          packages=get_packages(),
          scripts=get_scripts())


if __name__ == '__main__':
    run()
