# pylint: disable=E0611
import os
from distutils.core import setup

try:
    import autotest.common as common  # pylint: disable=W0611
except ImportError:
    import common  # pylint: disable=W0611

from autotest.client.shared import version

# Mostly needed when called one level up
if os.path.isdir('server'):
    server_dir = 'server'
else:
    server_dir = '.'


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


def get_file_list():
    # Some stuff is too hard to package. just grab every file in these directories
    # and call it a day.  we can clean up some other time
    pd_filelist = []
    pd_filelist.extend(_get_files(os.path.join(server_dir, 'control_segments')))
    return pd_filelist


def get_package_dir():
    return {'autotest.server': server_dir}


def get_package_data():
    return {'autotest.server': get_file_list()}


def get_packages():
    return ['autotest.server.hosts',
            'autotest.server.hosts.monitors',
            'autotest.server']


def get_scripts():
    return [server_dir + '/autotest-remote']


def run():
    setup(name='autotest',
          description='Autotest testing framework - remote module',
          maintainer='Lucas Meneghel Rodrigues',
          author_email='lmr@redhat.com',
          version=version.get_version(),
          url='http://autotest.github.com',
          package_dir=get_package_dir(),
          package_data=get_package_data(),
          packages=get_packages(),
          scripts=get_scripts())


if __name__ == '__main__':
    run()
