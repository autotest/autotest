from distutils.core import setup
import os, sys

try:
    import autotest.common as common
except ImportError:
    import common

from autotest_lib.client.common_lib import version

# Mostly needed when called one level up
db_dir = os.path.dirname(sys.modules[__name__].__file__) or '.'
autotest_dir = os.path.abspath(os.path.join(db_dir, ".."))

setup(name='autotest',
      description='Autotest test framework - results database module',
      author='Autotest Team',
      author_email='autotest@test.kernel.org',
      version=version.get_git_version(),
      url='autotest.kernel.org',
      package_dir={'autotest.database': db_dir },
      package_data={'autotest.database' : ['*.sql' ] },
      packages=['autotest.database' ],
      scripts=[db_dir + '/autotest-upgrade-db'],
)
