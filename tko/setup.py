from distutils.core import setup
import os

try:
    import autotest.common as common
except ImportError:
    import common

from autotest.client.shared import version

# Mostly needed when called one level up
if os.path.isdir('tko'):
    tko_dir = 'tko'
else:
    tko_dir = '.'

# TODO: add some toplevel non-python files

def get_package_dir():
    return {'autotest.tko': tko_dir}

def get_package_data():
    return {'autotest.tko' : get_filelist()}

def _get_files(path):
    '''
    Given a path, return all the files in there to package
    '''
    flist=[]
    for root, _, files in sorted(os.walk(path)):
        for name in files:
            fullname = os.path.join(root, name)
            flist.append(fullname)
    return flist


def get_filelist():
    pd_filelist=_get_files(os.path.join(tko_dir, 'parsers'))
    return pd_filelist


def get_packages():
    return ['autotest.tko.parsers',
            'autotest.tko.parsers.test',
            'autotest.tko.parsers.test.templates',
            'autotest.tko']

def get_data_files():
    return [('share/autotest/tko', [tko_dir + '/tko.proto'])]


def get_scripts():
    return [tko_dir + '/autotest-db-delete-job',
            tko_dir + '/autotest-tko-parse']


def run():
    setup(name='autotest',
          description='Autotest testing framework - TKO module',
          maintainer='Lucas Meneghel Rodrigues',
          maintainer_email='lmr@redhat.com',
          version=version.get_version(),
          url='http://autotest.github.com',
          package_dir=get_package_dir(),
          packages=get_packages(),
          data_files=get_data_files(),
          scripts=get_scripts())


if __name__ == '__main__':
    run()
