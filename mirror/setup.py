# pylint: disable=E0611
import os
from distutils.core import setup

try:
    import autotest.common as common  # pylint: disable=W0611
except ImportError:
    import common  # pylint: disable=W0611

from autotest.client.shared import version

# Mostly needed when called one level up
if os.path.isdir('mirror'):
    mirror_dir = 'mirror'
else:
    mirror_dir = '.'


def get_package_dir():
    return {'autotest.mirror': mirror_dir}


def get_packages():
    return ['autotest.mirror']


def get_data_files():
    return [('share/autotest/mirror', [mirror_dir + '/mirror'])]


def run():
    setup(name='autotest',
          description='Autotest testing framework - mirror module',
          author='Autotest Team',
          author_email='autotest@test.kernel.org',
          version=version.get_version(),
          url='autotest.kernel.org',
          package_dir=get_package_dir(),
          packages=get_packages(),
          data_files=get_data_files())


if __name__ == '__main__':
    run()
