from distutils.core import setup
import os, sys

try:
    import autotest.common as common
except ImportError:
    import common

from autotest_lib.client.common_lib import version

# Mostly needed when called one level up
utils_dir = os.path.dirname(sys.modules[__name__].__file__) or '.'

# TODO handle the init scripts

setup(name='autotest',
      description='Autotest testing framework - utility scripts',
      author='Autotest Team',
      author_email='autotest@test.kernel.org',
      version=version.get_git_version(),
      url='autotest.kernel.org',
      package_dir={'autotest.utils': utils_dir },
      package_data={'autotest.utils' : ['named_semaphore/*',
                                        'modelviz/*',
                                       ],
                   },
      packages=['autotest.utils'],
      data_files=[('share/autotest/utils', [ utils_dir + '/autotestd.service',
                                             utils_dir + '/autotest.init',
                                             utils_dir + '/autotest-rh.init',
                                             utils_dir + '/release'
                                           ])
                 ],
)
