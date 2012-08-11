"""
Module that deals with dependencies for tests, including executables,
packages and even permissions.
"""

import os, stat

from autotest.client.shared import software_manager


__all__ = ['DependencyNotSatisfied',
           'get_executable_path',
           'has_executable_bits',
           'has_executable',
           'can_execute',
           'executable',
           'has_package',
           'package']


class DependencyNotSatisfied(Exception):
    '''
    Exception raised when a dependency is not satisfied
    '''
    pass


def get_executable_path(name):
    '''
    Returns the path for an executable file

    The executable is searched for throught the currently define PATH.
    If executable already is an absolute path, then it is returned verbatim.

    :param executable: the full path or base name of an executable
    :type executable: string
    :returns: the executable full path or None if it's not found on PATH
    :rtype: str or None
    '''
    if os.path.isabs(name):
        return name
    else:
        for path in os.environ['PATH'].split(':'):
            full_path = os.path.join(path, name)
            if os.path.exists(full_path):
                return full_path
    return None


def has_executable_bits(path):
    '''
    Checks if the file has at least one of the executable bits set

    This does not check if the current user has permissions to execute the
    file, just checks if any of the executable bits are set.

    :param path: the full path of a file to check for executable bits
    :type path: string
    :returns: True if the file has at least on executable bit set, False
              otherwise
    '''
    mode = os.stat(path).st_mode
    has_x_bits = (mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH) > 0)
    return has_x_bits


def has_executable(name):
    '''
    Returns whether the system has a given executable

    If only the base name of the executable is given, then it's searched for
    throught the currently defined PATH. If a full path name is used, then
    only the other checks (making sure the file is indeed executable) are
    performed.

    :param name: the full path or base name of an executable
    :type name: string
    :returns: True if the file exists and has executable bits set, False
              otherwise
    '''
    path = get_executable_path(name)
    if path is None:
        return False
    return has_executable_bits(path)


def can_execute(name):
    '''
    Returns whether the current user can execute a given file

    This implies all the previous checks done by has_executable()

    :param name: the full path or base name of an executable
    :type name: string
    :returns: True if the file exists and can be executed
    '''
    path = get_executable_path(name)
    if path is None:
        return False
    return os.access(path, os.R_OK | os.X_OK)


def executable(name):
    '''
    Checks if the executable exists and can be executed

    This is a replacement for :func:`autotest.client.shared.os_dep.command`

    :param name: the executable name as it should be in the filesystem
    :type name: str
    :raises: DependencyNotSatisfied
    '''
    path = get_executable_path(name)
    if path is None:
        raise DependencyNotSatisfied('Executable "%s" not found' % name)

    satisfied = can_execute(name)
    if not satisfied:
        msg = ('Executable "%s" found, but permissions prevent it from being '
               'executed' % name)
        raise DependencyNotSatisfied(msg)

    return path


def has_package(name, version=None, arch=None):
    '''
    Utility function that queries if the given package installed

    :param name: the executable name as it should be in the filesystem
    :type name: str
    :param version: version of the package
    :type version: str
    :param arch: architecture of the package
    :type version: str
    :returns: True if the given package is installed, False otherwise
    '''
    package_manager = software_manager.SoftwareManager()
    return package_manager.check_installed(name, version, arch)


def package(name, version=None, arch=None):
    '''
    Checks if the given package installed

    :param name: the executable name as it should be in the filesystem
    :type name: str
    :param version: version of the package
    :type version: str
    :param arch: architecture of the package
    :type version: str
    :returns: None
    :raises: DependencyNotSatisfied
    '''
    satisfied = has_package(name, version, arch)
    if not satisfied:
        msg = 'Package "%s"' % name
        if version is not None:
            msg = '%s version "%s"' % (msg, version)
        if arch is not None:
            msg = '%s arch "%s"' % (msg, arch)
        msg = '%s not found' % msg
        raise DependencyNotSatisfied(msg)
