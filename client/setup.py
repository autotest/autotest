# pylint: disable=E0611
import os
from distutils.core import setup

try:
    import autotest.common as common  # pylint: disable=W0611
except ImportError:
    import common  # pylint: disable=W0611

from autotest.client.shared import version

# Mostly needed when called one level up
if os.path.isdir('client'):
    client_dir = 'client'
else:
    client_dir = '.'

autotest_dir = os.path.join(client_dir, "..")


def _get_files(path):
    '''
    Given a path, return all the files in there to package
    '''
    flist = []
    for root, _, files in sorted(os.walk(path)):
        for name in files:
            fullname = os.path.join(root, name)
            flist.append(fullname)
    return flist


def get_filelist():
    pd_filelist = ['config/*']
    pd_filelist.extend(_get_files(os.path.join(client_dir, 'profilers')))
    pd_filelist.extend(_get_files(os.path.join(client_dir, 'tools')))
    pd_filelist.extend(_get_files(os.path.join(client_dir, 'shared', 'templates')))
    return pd_filelist


def get_packages():
    return ['autotest.client.shared',
            'autotest.client.shared.hosts',
            'autotest.client.shared.backports',
            'autotest.client.shared.backports.collections',
            'autotest.client.shared.test_utils',
            'autotest.client.net',
            'autotest.client.tools',
            'autotest.client.profilers',
            'autotest.client',
            'autotest']


def get_scripts():
    return [os.path.join(client_dir, 'autotest-local'),
            os.path.join(client_dir, 'autotest-local-streamhandler'),
            os.path.join(client_dir, 'autotest-daemon'),
            os.path.join(client_dir, 'autotest-daemon-monitor')]


def get_data_files():
    return [(os.environ.get('AUTOTEST_TOP_PATH', '/etc/autotest'),
             [autotest_dir + '/global_config.ini',
              autotest_dir + '/shadow_config.ini', ]), ]


def get_package_dir():
    return {'autotest.client': client_dir, 'autotest': autotest_dir}


def get_package_data():
    return {'autotest.client': get_filelist()}


def run():
    setup(name='autotest',
          description='Autotest test framework - local module',
          maintainer='Lucas Meneghel Rodrigues',
          author_email='lmr@redhat.com',
          version=version.get_version(),
          url='http://autotest.github.com',
          package_dir=get_package_dir(),
          package_data=get_package_data(),
          packages=get_packages(),
          scripts=get_scripts(),
          data_files=get_data_files())


if __name__ == '__main__':
    run()
