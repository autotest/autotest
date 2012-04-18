from distutils.core import setup
import os, sys

try:
    import autotest.common as common
except ImportError:
    import common

from autotest.client.shared import version

# Mostly needed when called one level up
mirror_dir = os.path.dirname(sys.modules[__name__].__file__) or '.'
autotest_dir = os.path.abspath(os.path.join(mirror_dir, ".."))

setup(name='autotest',
      description='Autotest testing framework - mirror module',
      author='Autotest Team',
      author_email='autotest@test.kernel.org',
      version=version.get_git_version(),
      url='autotest.kernel.org',
      package_dir={'autotest.mirror': mirror_dir },
      packages=['autotest.mirror' ],
      data_files=[('share/autotest/mirror', [ mirror_dir + '/mirror' ])],
)
