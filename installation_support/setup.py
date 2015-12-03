# pylint: disable=E0611
import os
from distutils.core import setup

try:
    import autotest.common as common  # pylint: disable=W0611
except ImportError:
    import common  # pylint: disable=W0611

from autotest.client.shared import version

# Mostly needed when called one level up
if os.path.isdir('installation_support'):
    pkg_dir = 'installation_support'
else:
    pkg_dir = '.'


def get_package_dir():
    return {'autotest.installation_support': pkg_dir}


def get_scripts():
    return [os.path.join(pkg_dir, 'autotest-database-turnkey'),
            os.path.join(pkg_dir, 'autotest-firewalld-add-service'),
            os.path.join(pkg_dir, 'autotest-install-packages-deps')]


def get_packages():
    return ['autotest.installation_support',
            'autotest.installation_support.database_manager']


def run():
    setup(name='autotest',
          description='Autotest test framework - installation support',
          maintainer='Lucas Meneghel Rodrigues',
          author_email='lmr@redhat.com',
          version=version.get_version(),
          url='http://autotest.github.com',
          package_dir=get_package_dir(),
          packages=get_packages(),
          scripts=get_scripts())


if __name__ == '__main__':
    run()
