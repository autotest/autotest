from distutils.core import setup
import os, sys

try:
    import autotest.common as common
except ImportError:
    import common

from autotest.client.common_lib import version

# Mostly needed when called one level up
cli_dir = os.path.dirname(sys.modules[__name__].__file__) or '.'
autotest_dir = os.path.abspath(os.path.join(cli_dir, ".."))

setup(name='autotest',
      description='Autotest framework - cli interface to rpc server',
      author='Autotest Team',
      author_email='autotest@test.kernel.org',
      version=version.get_git_version(),
      url='autotest.kernel.org',
      package_dir={'autotest.cli': cli_dir },
      package_data={'autotest.cli' : ['contrib/*' ] },
      packages=['autotest.cli' ],
      scripts=[cli_dir + '/autotest-rpc-client',
               cli_dir + '/autotest-rpc-change-protection-level',
               cli_dir + '/autotest-rpc-compose-query',
               cli_dir + '/autotest-rpc-migrate-host',
               cli_dir + '/autotest-rpc-query-keyvals',
               cli_dir + '/autotest-rpc-query-results',
              ],
)
