from distutils.core import setup
import os

try:
    import autotest.common as common
except ImportError:
    import common

from autotest.client.shared import version

# Mostly needed when called one level up
if os.path.isdir('database'):
    db_dir = 'database'
else:
    db_dir = '.'


def get_package_dir():
    return {'autotest.database': db_dir}


def get_package_data():
    return {'autotest.database' : ['*.sql' ]}


def get_packages():
    return ['autotest.database']


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
