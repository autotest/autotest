# pylint: disable=E0611
import os
from distutils.core import setup

try:
    import autotest.common as common  # pylint: disable=W0611
except ImportError:
    import common  # pylint: disable=W0611

from autotest.client.shared import version

# mostly needed when called one level up
if os.path.isdir('scheduler'):
    scheduler_dir = 'scheduler'
else:
    scheduler_dir = '.'


def get_package_dir():
    return {'autotest.scheduler': scheduler_dir}


def get_package_data():
    return {'autotest.scheduler': ['archive_results.control.srv']}


def get_packages():
    return ['autotest.scheduler']


def get_scripts():
    return [os.path.join(scheduler_dir, 'autotest-scheduler'),
            os.path.join(scheduler_dir, 'autotest-scheduler-watcher')]


def run():
    setup(name='autotest',
          description='Autotest testing framework - scheduler module',
          maintainer='Lucas Meneghel Rodrigues',
          maintainer_email='lmr@redhat.com',
          version=version.get_version(),
          url='http://autotest.github.com',
          package_dir=get_package_dir(),
          package_data=get_package_data(),
          packages=get_packages(),
          scripts=get_scripts())


if __name__ == "__main__":
    run()
