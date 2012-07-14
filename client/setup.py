from distutils.core import setup
import os, sys

try:
    import autotest.common as common
except ImportError:
    import common

from autotest.client.shared import version

# Mostly needed when called one level up
client_dir = os.path.dirname(sys.modules[__name__].__file__) or '.'
autotest_dir = os.path.abspath(os.path.join(client_dir, ".."))

def get_data_files(path):
    '''
    Given a path, return all the files in there to package
    '''
    flist=[]
    for root, _, files in sorted(os.walk(path)):
        for name in files:
            fullname = os.path.join(root, name)
            flist.append(fullname)
    return flist

# Some stuff is too hard to package. just grab every file in these directories
# and call it a day.  we can clean up some other time
pd_filelist=['virt/scripts/*.py', 'virt/*.sample', 'virt/passfd.c', 'config/*' ]
pd_filelist.extend(get_data_files(os.path.join(client_dir, 'profilers')))
pd_filelist.extend(get_data_files(os.path.join(client_dir, 'samples')))
pd_filelist.extend(get_data_files(os.path.join(client_dir, 'tests')))
pd_filelist.extend(get_data_files(os.path.join(client_dir, 'virt', 'autoit')))
pd_filelist.extend(get_data_files(os.path.join(client_dir, 'virt', 'autotest_control')))
pd_filelist.extend(get_data_files(os.path.join(client_dir, 'virt', 'blkdebug')))
pd_filelist.extend(get_data_files(os.path.join(client_dir, 'virt', 'deps')))
pd_filelist.extend(get_data_files(os.path.join(client_dir, 'virt', 'steps')))
pd_filelist.extend(get_data_files(os.path.join(client_dir, 'virt', 'tests')))
pd_filelist.extend(get_data_files(os.path.join(client_dir, 'virt', 'unattended')))
pd_filelist.extend(get_data_files(os.path.join(client_dir, 'tools')))


setup(name='autotest',
      description='Autotest test framework - local module',
      author='Autotest Team',
      author_email='autotest@test.kernel.org',
      version=version.get_git_version(),
      url='autotest.kernel.org',
      package_dir={'autotest.client': client_dir,
                   'autotest' : autotest_dir,
                  },
      package_data={'autotest.client' : pd_filelist },
      packages=['autotest.client.shared',
                'autotest.client.shared.hosts',
                'autotest.client.shared.test_utils',
                'autotest.client.net',
                'autotest.client.tools',
                'autotest.client.profilers',
                'autotest.client.tests',
                'autotest.client.site_tests',
                'autotest.client.virt',
                'autotest.client',
                'autotest',
               ],
      scripts=[os.path.join(client_dir, 'autotest-local')],
      data_files=[('/etc/autotest', [autotest_dir + '/global_config.ini',
                                     autotest_dir + '/shadow_config.ini',
                                   ]),
                 ],
)
