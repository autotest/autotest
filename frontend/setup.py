# pylint: disable=E0611
import os
from distutils.core import setup

try:
    import autotest.common as common  # pylint: disable=W0611
except ImportError:
    import common  # pylint: disable=W0611

from autotest.client.shared import version

# Mostly needed when called one level up
if os.path.isdir('frontend'):
    fe_dir = 'frontend'
else:
    fe_dir = '.'

# TODO: handle the client directory


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
    pd_filelist.extend(_get_files(os.path.join(fe_dir, 'client')))
    pd_filelist.extend(_get_files(os.path.join(fe_dir, 'afe', 'doctests')))
    pd_filelist.extend(_get_files(os.path.join(fe_dir, 'afe', 'fixtures')))
    pd_filelist.extend(_get_files(os.path.join(fe_dir, 'afe', 'migrations')))
    pd_filelist.extend(_get_files(os.path.join(fe_dir, 'afe', 'templates')))
    pd_filelist.extend(_get_files(os.path.join(fe_dir, 'tko', 'fixtures')))
    pd_filelist.extend(_get_files(os.path.join(fe_dir, 'tko', 'migrations')))
    pd_filelist.extend(_get_files(os.path.join(fe_dir, 'tko', 'sql')))
    pd_filelist.extend(_get_files(os.path.join(fe_dir, 'static')))
    pd_filelist.extend(_get_files(os.path.join(fe_dir, 'templates')))
    pd_filelist.extend(_get_files(os.path.join(fe_dir, 'tko', 'preconfigs')))
    pd_filelist.extend([os.path.join(fe_dir, 'frontend.wsgi')])
    return pd_filelist


def get_package_dir():
    return {'autotest.frontend': fe_dir}


def get_package_data():
    return {'autotest.frontend': get_file_list()}


def get_scripts():
    return [os.path.join(fe_dir, 'autotest-manage-rpc-server')]


def get_packages():
    return ['autotest.frontend.afe',
            'autotest.frontend.afe.feeds',
            'autotest.frontend.afe.json_rpc',
            'autotest.frontend.db',
            'autotest.frontend.db.backends',
            'autotest.frontend.db.backends.afe',
            'autotest.frontend.db.backends.afe_sqlite',
            'autotest.frontend.shared',
            'autotest.frontend.tko',
            'autotest.frontend']


def run():
    setup(name='autotest',
          description='Autotest test framework - RPC server',
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
