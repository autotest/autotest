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

pd_filelist=['config/*' ]
pd_filelist.extend(get_data_files(os.path.join(client_dir, 'profilers')))
pd_filelist.extend(get_data_files(os.path.join(client_dir, 'tests')))
pd_filelist.extend(get_data_files(os.path.join(client_dir, 'tools')))

def run():
    setup(name='autotest',
          description='Autotest test framework - local module',
          author='Autotest Team',
          author_email='autotest@test.kernel.org',
          version=version.get_version(),
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
                    'autotest.client',
                    'autotest',
                   ],
          scripts=[os.path.join(client_dir, 'autotest-local'),
                   os.path.join(client_dir, 'autotest-local-streamhandler'),
                   os.path.join(client_dir, 'autotest-daemon'),
                   os.path.join(client_dir, 'autotest-daemon-monitor')],
          data_files=[('/etc/autotest', [autotest_dir + '/global_config.ini',
                                         autotest_dir + '/shadow_config.ini',
                                       ]),
                     ],
    )

if __name__ == '__main__':
    run()
