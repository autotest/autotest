"""
This module provides the client facilities to detect the Linux Distribution
it's running under.

This is a replacement for the get_os_vendor() function from the utils module.
"""

import os
import platform
import re

__all__ = ['LinuxDistro',
           'UNKNOWN_DISTRO_NAME',
           'UNKNOWN_DISTRO_VERSION',
           'UNKNOWN_DISTRO_RELEASE',
           'UNKNOWN_DISTRO_ARCH',
           'Probe',
           'register_probe',
           'detect']


# pylint: disable=R0903
class LinuxDistro(object):

    '''
    Simple collection of information for a Linux Distribution
    '''

    def __init__(self, name, version, release, arch):
        '''
        Initializes a new Linux Distro

        :param name: a short name that precisely distinguishes this Linux
                     Distribution among all others.
        :type name: str
        :param version: the major version of the distribution. Usually this
                        is a single number that denotes a large development
                        cycle and support file.
        :type version: str
        :param release: the release or minor version of the distribution.
                        Usually this is also a single number, that is often
                        omitted or starts with a 0 when the major version
                        is initially release. It's ofter associated with a
                        shorter development cycle that contains incremental
                        a collection of improvements and fixes.
        :type release: str
        :param arch: the main target for this Linux Distribution. It's common
                     for some architectures to ship with packages for
                     previous and still compatible architectures, such as it's
                     the case with Intel/AMD 64 bit architecture that support
                     32 bit code. In cases like this, this should be set to
                     the 64 bit architecture name.
        :type arch: str
        '''
        self.name = name
        self.version = version
        self.release = release
        self.arch = arch

    def __repr__(self):
        return '<LinuxDistro: name=%s, version=%s, release=%s, arch=%s>' % (
            self.name, self.version, self.release, self.arch)


UNKNOWN_DISTRO_NAME = 'unknown'
UNKNOWN_DISTRO_VERSION = 0
UNKNOWN_DISTRO_RELEASE = 0
UNKNOWN_DISTRO_ARCH = 'unknown'


#: The distribution that is used when the exact one could not be found
UNKNOWN_DISTRO = LinuxDistro(UNKNOWN_DISTRO_NAME,
                             UNKNOWN_DISTRO_VERSION,
                             UNKNOWN_DISTRO_RELEASE,
                             UNKNOWN_DISTRO_ARCH)


class Probe(object):

    '''
    Probes the machine and does it best to confirm it's the right distro
    '''
    #: Points to a file that can determine if this machine is running a given
    #: Linux Distribution. This servers a first check that enables the extra
    #: checks to carry on.
    CHECK_FILE = None

    #: Sets the content that should be checked on the file pointed to by
    #: :attr:`CHECK_FILE_EXISTS`. Leave it set to `None` (its default)
    #: to check only if the file exists, and not check its contents
    CHECK_FILE_CONTAINS = None

    #: The name of the Linux Distribution to be returned if the file defined
    #: by :attr:`CHECK_FILE_EXISTS` exist.
    CHECK_FILE_DISTRO_NAME = None

    #: A regular expresion that will be run on the file pointed to by
    #: :attr:`CHECK_FILE_EXISTS`
    CHECK_VERSION_REGEX = None

    def __init__(self):
        self.score = 0

    def check_name_for_file(self):
        '''
        Checks if this class will look for a file and return a distro

        The conditions that must be true include the file that identifies the
        distro file being set (:attr:`CHECK_FILE`) and the name of the
        distro to be returned (:attr:`CHECK_FILE_DISTRO_NAME`)
        '''
        if self.CHECK_FILE is None:
            return False

        if self.CHECK_FILE_DISTRO_NAME is None:
            return False

        return True

    def name_for_file(self):
        '''
        Get the distro name if the :attr:`CHECK_FILE` is set and exists
        '''
        if self.check_name_for_file():
            if os.path.exists(self.CHECK_FILE):
                return self.CHECK_FILE_DISTRO_NAME

    def check_name_for_file_contains(self):
        '''
        Checks if this class will look for text on a file and return a distro

        The conditions that must be true include the file that identifies the
        distro file being set (:attr:`CHECK_FILE`), the text to look for
        inside the distro file (:attr:`CHECK_FILE_CONTAINS`) and the name
        of the distro to be returned (:attr:`CHECK_FILE_DISTRO_NAME`)
        '''
        if self.CHECK_FILE is None:
            return False

        if self.CHECK_FILE_CONTAINS is None:
            return False

        if self.CHECK_FILE_DISTRO_NAME is None:
            return False

        return True

    def name_for_file_contains(self):
        '''
        Get the distro if the :attr:`CHECK_FILE` is set and has content
        '''
        if self.check_name_for_file_contains():
            if os.path.exists(self.CHECK_FILE):
                for line in open(self.CHECK_FILE).readlines():
                    if self.CHECK_FILE_CONTAINS in line:
                        return self.CHECK_FILE_DISTRO_NAME

    def check_version(self):
        '''
        Checks if this class will look for a regex in file and return a distro
        '''
        if self.CHECK_FILE is None:
            return False

        if self.CHECK_VERSION_REGEX is None:
            return False

        return True

    def _get_version_match(self):
        '''
        Returns the match result for the version regex on the file content
        '''
        if self.check_version():
            if os.path.exists(self.CHECK_FILE):
                version_file_content = open(self.CHECK_FILE).read()
            else:
                return None

            return self.CHECK_VERSION_REGEX.match(version_file_content)

    def version(self):
        '''
        Returns the version of the distro
        '''
        version = UNKNOWN_DISTRO_VERSION
        match = self._get_version_match()
        if match is not None:
            if match.groups() > 0:
                version = match.groups()[0]
        return version

    def check_release(self):
        '''
        Checks if this has the conditions met to look for the release number
        '''
        return (self.check_version() and
                self.CHECK_VERSION_REGEX.groups > 1)

    def release(self):
        '''
        Returns the release of the distro
        '''
        release = UNKNOWN_DISTRO_RELEASE
        match = self._get_version_match()
        if match is not None:
            if match.groups() > 1:
                release = match.groups()[1]
        return release

    def get_distro(self):
        '''
        Returns the :class:`LinuxDistro` this probe detected
        '''
        name = None
        version = UNKNOWN_DISTRO_VERSION
        release = UNKNOWN_DISTRO_RELEASE
        arch = UNKNOWN_DISTRO_ARCH

        distro = None

        if self.check_name_for_file():
            name = self.name_for_file()
            self.score += 1

        if self.check_name_for_file_contains():
            name = self.name_for_file_contains()
            self.score += 1

        if self.check_version():
            version = self.version()
            self.score += 1

        if self.check_release():
            release = self.release()
            self.score += 1

        # can't think of a better way to do this
        arch = os.uname()[4]

        # name is the first thing that should be identified. If we don't know
        # the distro name, we don't bother checking for versions
        if name is not None:
            distro = LinuxDistro(name, version, release, arch)
        else:
            distro = UNKNOWN_DISTRO

        return distro


class StdLibProbe(Probe):

    '''
    Probe that uses the Python standard library builtin detection

    This Probe has a lower score on purporse, serving as a fallback
    if no explicit (and hopefully more accurate) probe exists.
    '''

    def get_distro(self):
        name = None
        version = UNKNOWN_DISTRO_VERSION
        release = UNKNOWN_DISTRO_RELEASE
        arch = UNKNOWN_DISTRO_ARCH

        d_name, d_version_release, d_codename = platform.dist()
        if d_name:
            name = d_name

        if '.' in d_version_release:
            d_version, d_release = d_version_release.split('.', 1)
            version = d_version
            release = d_release
        else:
            version = d_version_release

        arch = os.uname()[4]

        if name is not None:
            distro = LinuxDistro(name, version, release, arch)
        else:
            distro = UNKNOWN_DISTRO

        return distro


class RedHatProbe(Probe):

    '''
    Probe with version checks for Red Hat Enterprise Linux systems
    '''
    CHECK_FILE = '/etc/redhat-release'
    CHECK_FILE_CONTAINS = 'Red Hat'
    CHECK_FILE_DISTRO_NAME = 'redhat'
    CHECK_VERSION_REGEX = re.compile(
        r'Red Hat Enterprise Linux Server release (\d{1,2})\.(\d{1,2}).*')


class CentosProbe(RedHatProbe):

    '''
    Probe with version checks for CentOS systems
    '''
    CHECK_FILE = '/etc/redhat-release'
    CHECK_FILE_CONTAINS = 'CentOS'
    CHECK_FILE_DISTRO_NAME = 'centos'
    CHECK_VERSION_REGEX = re.compile(r'CentOS release (\d{1,2})\.(\d{1,2}).*')


class FedoraProbe(RedHatProbe):

    '''
    Probe with version checks for Fedora systems
    '''
    CHECK_FILE = '/etc/fedora-release'
    CHECK_FILE_CONTAINS = 'Fedora'
    CHECK_FILE_DISTRO_NAME = 'fedora'
    CHECK_VERSION_REGEX = re.compile(r'Fedora release (\d{1,2}).*')


class DebianProbe(Probe):

    '''
    Simple probe with file checks for Debian systems
    '''
    CHECK_FILE = '/etc/debian-version'
    CHECK_FILE_DISTRO_NAME = 'debian'


class UbuntuProbe(Probe):

    '''
    Simple probe with file checks for Ubuntu systems
    '''
    CHECK_FILE = '/etc/os-release'
    CHECK_FILE_CONTAINS = 'Ubuntu'
    CHECK_FILE_DISTRO_NAME = 'ubuntu'
    CHECK_VERSION_REGEX = re.compile(r'VERSION_ID="(\d+.\d+)"')


class SuseProbe(Probe):
    CHECK_FILE = '/etc/SuSE-release'
    CHECK_FILE_DISTRO_NAME = 'sles'
    CHECK_VERSION_REGEX = re.compile(r'SUSE.*\nVERSION = (.*)\nPATCHLEVEL = (.*)')


#: the complete list of probes that have been registered
REGISTERED_PROBES = []


def register_probe(probe_class):
    '''
    Register a probe to be run during autodetection
    '''
    if probe_class not in REGISTERED_PROBES:
        REGISTERED_PROBES.append(probe_class)


register_probe(RedHatProbe)
register_probe(CentosProbe)
register_probe(FedoraProbe)
register_probe(DebianProbe)
register_probe(UbuntuProbe)
register_probe(SuseProbe)
register_probe(StdLibProbe)


def detect():
    '''
    Attempts to detect the Linux Distribution running on this machine

    :returns: the detected :class:`LinuxDistro` or :data:`UNKNOWN_DISTRO`
    :rtype: :class:`LinuxDistro`
    '''
    results = []

    for probe_class in REGISTERED_PROBES:
        probe_instance = probe_class()
        distro_result = probe_instance.get_distro()
        if distro_result is not UNKNOWN_DISTRO:
            results.append((distro_result, probe_instance))

    results.sort(key=lambda t: t[1].score)
    if len(results) > 0:
        distro = results[-1][0]
    else:
        distro = UNKNOWN_DISTRO

    return distro


class Spec(object):

    '''
    Describes a distro, usually for setting minimum distro requirements
    '''

    def __init__(self, name, min_version=None, min_release=None, arch=None):
        self.name = name
        self.min_version = min_version
        self.min_release = min_release
        self.arch = arch
