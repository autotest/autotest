# pylint: disable=E0611
from distutils.core import setup
import os

try:
    import autotest.common as common
except ImportError:
    import common

from autotest.client.shared import version

# Mostly needed when called one level up
if os.path.isdir('shared'):
    pkg_dir = 'shared'
else:
    pkg_dir = '.'


def get_package_dir():
    return {'autotest.shared': pkg_dir}


def get_packages():
    return ['autotest.shared']


def run():
    setup(name='autotest',
          description='Autotest test framework - common definitions',
          maintainer='Lucas Meneghel Rodrigues',
          author_email='lmr@redhat.com',
          version=version.get_version(),
          url='http://autotest.github.com',
          package_dir=get_package_dir(),
          packages=get_packages())


if __name__ == '__main__':
    run()
