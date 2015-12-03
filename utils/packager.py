#!/usr/bin/python -u

"""
Utility to upload or remove the packages from the packages repository.
"""

import logging
import optparse
import os
import shutil
import sys
import tempfile

try:
    import autotest.common as common  # pylint: disable=W0611
except ImportError:
    import common  # pylint: disable=W0611
from autotest.client.shared import utils as client_utils
from autotest.client.shared import error
from autotest.client.shared.settings import settings
from autotest.client.shared import base_packages, packages
from autotest.server import utils as server_utils

logging.basicConfig(level=logging.DEBUG)


def get_exclude_string(client_dir):
    '''
    Get the exclude string for the tar command to exclude specific
    subdirectories inside client_dir.
    For profilers we need to exclude everything except the __ini__.py
    file so that the profilers can be imported.
    '''
    exclude_string = ('--exclude=deps/* --exclude=tests/* '
                      '--exclude=site_tests/*')

    # Get the profilers directory
    prof_dir = os.path.join(client_dir, 'profilers')

    # Include the __init__.py file for the profilers and exclude all its
    # subdirectories
    for f in os.listdir(prof_dir):
        if os.path.isdir(os.path.join(prof_dir, f)):
            exclude_string += ' --exclude=profilers/%s' % f

    return exclude_string


def parse_args():
    parser = optparse.OptionParser()
    parser.add_option("-d", "--dependency", help="package the dependency"
                      " from client/deps directory and upload to the repo",
                      dest="dep")
    parser.add_option("-p", "--profiler", help="package the profiler "
                      "from client/profilers directory and upload to the repo",
                      dest="prof")
    parser.add_option("-t", "--test", help="package the test from client/tests"
                      " or client/site_tests and upload to the repo.",
                      dest="test")
    parser.add_option("-c", "--client", help="package the client "
                      "directory alone without the tests, deps and profilers",
                      dest="client", action="store_true", default=False)
    parser.add_option("-f", "--file", help="simply uploads the specified"
                      "file on to the repo", dest="file")
    parser.add_option("-r", "--repository", help="the URL of the packages"
                      "repository location to upload the packages to.",
                      dest="repo", default=None)
    parser.add_option("--all", help="Upload all the files locally "
                      "to all the repos specified in global_config.ini. "
                      "(includes the client, tests, deps and profilers)",
                      dest="all", action="store_true", default=False)

    options, args = parser.parse_args()
    return options, args


# Method to upload or remove package depending on the flag passed to it.
def process_packages(pkgmgr, pkg_type, pkg_names, src_dir,
                     remove=False):
    include_string = " ."
    exclude_string = None
    names = [p.strip() for p in pkg_names.split(',')]
    for name in names:
        print "Processing %s ... " % name
        if pkg_type == 'client':
            pkg_dir = src_dir
            exclude_string = get_exclude_string(pkg_dir)
        elif pkg_type == 'test':
            # if the package is a test then look whether it is in client/tests
            # or client/site_tests
            pkg_dir = os.path.join(get_test_dir(name, src_dir), name)
        else:
            # for the profilers and deps
            pkg_dir = os.path.join(src_dir, name)

        pkg_name = pkgmgr.get_tarball_name(name, pkg_type)
        if not remove:
            # Tar the source and upload
            temp_dir = tempfile.mkdtemp()
            try:
                try:
                    base_packages.check_diskspace(temp_dir)
                except error.RepoDiskFullError, e:
                    msg = ("Temporary directory for packages %s does not have "
                           "enough space available: %s" % (temp_dir, e))
                    raise error.RepoDiskFullError(msg)
                tarball_path = pkgmgr.tar_package(pkg_name=pkg_name,
                                                  src_dir=pkg_dir,
                                                  dest_dir=temp_dir,
                                                  include_string=include_string,
                                                  exclude_string=exclude_string)
                pkgmgr.upload_pkg(tarball_path, update_checksum=True)
            finally:
                # remove the temporary directory
                shutil.rmtree(temp_dir)
        else:
            pkgmgr.remove_pkg(pkg_name, remove_checksum=True)
        print "Done."


def tar_packages(pkgmgr, pkg_type, pkg_names, src_dir, temp_dir):
    """Tar all packages up and return a list of each tar created"""
    tarballs = []
    include_string = ' .'
    exclude_string = None
    names = [p.strip() for p in pkg_names.split(',')]
    for name in names:
        print "Processing %s ... " % name
        if pkg_type == 'client':
            pkg_dir = src_dir
            exclude_string = get_exclude_string(pkg_dir)
        elif pkg_type == 'test':
            # if the package is a test then look whether it is in client/tests
            # or client/site_tests
            pkg_dir = os.path.join(get_test_dir(name, src_dir), name)
        else:
            # for the profilers and deps
            pkg_dir = os.path.join(src_dir, name)

        pkg_name = pkgmgr.get_tarball_name(name, pkg_type)
        tarball_path = pkgmgr.tar_package(pkg_name=pkg_name,
                                          src_dir=pkg_dir,
                                          dest_dir=temp_dir,
                                          include_string=include_string,
                                          exclude_string=exclude_string)

        tarballs.append(tarball_path)

    return tarballs


def process_all_packages(pkgmgr, client_dir, remove=False):
    """Process a full upload of packages as a directory upload."""
    dep_dir = os.path.join(client_dir, "deps")
    prof_dir = os.path.join(client_dir, "profilers")
    # Directory where all are kept
    temp_dir = tempfile.mkdtemp()
    try:
        base_packages.check_diskspace(temp_dir)
    except error.RepoDiskFullError, e:
        print ("Temp destination for packages is full %s, aborting upload: %s"
               % (temp_dir, e))
        os.rmdir(temp_dir)
        sys.exit(1)

    # process tests
    tests_list = get_subdir_list('tests', client_dir)
    tests = ','.join(tests_list)

    # process site_tests
    site_tests_list = get_subdir_list('site_tests', client_dir)
    site_tests = ','.join(site_tests_list)

    # process deps
    deps_list = get_subdir_list('deps', client_dir)
    deps = ','.join(deps_list)

    # process profilers
    profilers_list = get_subdir_list('profilers', client_dir)
    profilers = ','.join(profilers_list)

    # Update md5sum
    if not remove:
        tar_packages(pkgmgr, 'profiler', profilers, prof_dir, temp_dir)
        tar_packages(pkgmgr, 'dep', deps, dep_dir, temp_dir)
        tar_packages(pkgmgr, 'test', site_tests, client_dir, temp_dir)
        tar_packages(pkgmgr, 'test', tests, client_dir, temp_dir)
        tar_packages(pkgmgr, 'client', 'autotest', client_dir, temp_dir)
        cwd = os.getcwd()
        os.chdir(temp_dir)
        client_utils.system('md5sum * > packages.checksum')
        os.chdir(cwd)
        pkgmgr.upload_pkg(temp_dir)
        client_utils.run('rm -rf ' + temp_dir)
    else:
        process_packages(pkgmgr, 'test', tests, client_dir, remove=remove)
        process_packages(pkgmgr, 'test', site_tests, client_dir, remove=remove)
        process_packages(pkgmgr, 'client', 'autotest', client_dir,
                         remove=remove)
        process_packages(pkgmgr, 'dep', deps, dep_dir, remove=remove)
        process_packages(pkgmgr, 'profiler', profilers, prof_dir,
                         remove=remove)


# Get the list of sub directories present in a directory
def get_subdir_list(name, client_dir):
    dir_name = os.path.join(client_dir, name)
    return [f for f in
            os.listdir(dir_name)
            if os.path.isdir(os.path.join(dir_name, f))]


# Look whether the test is present in client/tests and client/site_tests dirs
def get_test_dir(name, client_dir):
    names_test = os.listdir(os.path.join(client_dir, 'tests'))
    names_site_test = os.listdir(os.path.join(client_dir, 'site_tests'))
    if name in names_test:
        src_dir = os.path.join(client_dir, 'tests')
    elif name in names_site_test:
        src_dir = os.path.join(client_dir, 'site_tests')
    else:
        print "Test %s not found" % name
        sys.exit(0)
    return src_dir


def main():
    # get options and args
    options, args = parse_args()

    server_dir = server_utils.get_server_dir()
    autotest_dir = os.path.abspath(os.path.join(server_dir, '..'))

    # extract the pkg locations from global config
    repo_urls = settings.get_value('PACKAGES', 'fetch_location',
                                   type=list, default=[])
    upload_paths = settings.get_value('PACKAGES', 'upload_location',
                                      type=list, default=[])

    if options.repo:
        upload_paths.append(options.repo)

    # Having no upload paths basically means you're not using packaging.
    if not upload_paths:
        print("No upload locations found. Please set upload_location under"
              " PACKAGES in the global_config.ini or provide a location using"
              " the --repository option.")
        return

    client_dir = os.path.join(autotest_dir, "client")

    # Bail out if the client directory does not exist
    if not os.path.exists(client_dir):
        sys.exit(0)

    dep_dir = os.path.join(client_dir, "deps")
    prof_dir = os.path.join(client_dir, "profilers")

    if len(args) == 0 or args[0] not in ['upload', 'remove']:
        print("Either 'upload' or 'remove' needs to be specified "
              "for the package")
        sys.exit(0)

    if args[0] == 'upload':
        remove_flag = False
    elif args[0] == 'remove':
        remove_flag = True
    else:
        # we should not be getting here
        assert(False)

    pkgmgr = packages.PackageManager(autotest_dir, repo_urls=repo_urls,
                                     upload_paths=upload_paths,
                                     run_function_dargs={'timeout': 600})

    if options.all:
        process_all_packages(pkgmgr, client_dir, remove=remove_flag)

    if options.client:
        process_packages(pkgmgr, 'client', 'autotest', client_dir,
                         remove=remove_flag)

    if options.dep:
        process_packages(pkgmgr, 'dep', options.dep, dep_dir,
                         remove=remove_flag)

    if options.test:
        process_packages(pkgmgr, 'test', options.test, client_dir,
                         remove=remove_flag)

    if options.prof:
        process_packages(pkgmgr, 'profiler', options.prof, prof_dir,
                         remove=remove_flag)

    if options.file:
        if remove_flag:
            pkgmgr.remove_pkg(options.file, remove_checksum=True)
        else:
            pkgmgr.upload_pkg(options.file, update_checksum=True)


if __name__ == "__main__":
    main()
