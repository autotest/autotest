# pylint: disable=E0611
import os
from distutils.core import setup

try:
    import autotest.common as common  # pylint: disable=W0611
except ImportError:
    import common  # pylint: disable=W0611

from autotest.client.shared import version

# Mostly needed when called one level up
if os.path.isdir('cli'):
    cli_dir = 'cli'
else:
    cli_dir = '.'


def get_package_dir():
    return {'autotest.cli': cli_dir}


def get_package_data():
    return {'autotest.cli': ['contrib/*']}


def get_packages():
    return ['autotest.cli']


def get_scripts():
    return [cli_dir + '/autotest-rpc-client',
            cli_dir + '/autotest-rpc-change-protection-level',
            cli_dir + '/autotest-rpc-migrate-host',
            cli_dir + '/autotest-rpc-query-keyvals',
            cli_dir + '/autotest-rpc-query-results']


def run():
    setup(name='autotest',
          description='Autotest framework - CLI interface to the RPC server',
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
