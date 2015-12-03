"""
This module defines a structure and portable format for relevant information
on Linux Distributions in such a way that information about known distros
can be packed and distributed.

Please note that this module deals with Linux Distributions not necessarily
installed on the running system.
"""

import bz2
import os
import pickle

from autotest.client import os_dep, utils
from autotest.client.shared import distro

__all__ = ['save', 'load', 'load_from_tree', 'SoftwarePackage', 'DistroDef',
           'DISTRO_PKG_INFO_LOADERS']


def save(linux_distro, path):
    '''
    Saves the linux_distro to an external file format

    :param linux_distro: an :class:`DistroDef` instance
    :type linux_distro: DistroDef
    :param path: the location for the output file
    :type path: str
    :return: None
    '''
    output = open(path, 'w')
    output.write(bz2.compress(pickle.dumps(linux_distro)))
    output.close()


def load(path):
    '''
    Loads the distro from an external file

    :param path: the location for the input file
    :type path: str
    :return: an :class:`DistroDef` instance
    :rtype: DistroDef
    '''
    return pickle.loads(bz2.decompress(open(path).read()))


# pylint: disable=I0011,R0913
def load_from_tree(name, version, release, arch,
                   package_type, path):
    '''
    Loads a DistroDef from an installable tree

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
    :param package_type: one of the available package info loader types
    :type package_type: str
    :param path: top level directory of the distro installation tree files
    :type path: str
    '''
    distro_def = DistroDef(name, version, release, arch)

    loader_class = DISTRO_PKG_INFO_LOADERS.get(package_type, None)
    if loader_class is not None:
        loader = loader_class(path)
        distro_def.software_packages = [SoftwarePackage(*args)
                                        for args in loader.get_packages_info()]
        distro_def.software_packages_type = package_type
    return distro_def


# pylint: disable=I0011,R0903
class SoftwarePackage(object):

    '''
    Definition of relevant information on a software package
    '''

    def __init__(self, name, version, release, checksum, arch):
        self.name = name
        self.version = version
        self.release = release
        self.checksum = checksum
        self.arch = arch


# pylint: disable=I0011,R0903
class DistroDef(distro.LinuxDistro):

    '''
    More complete information on a given Linux Distribution
    '''

    def __init__(self, name, version, release, arch):
        super(DistroDef, self).__init__(name, version, release, arch)

        #: All the software packages that ship with this Linux distro
        self.software_packages = []

        #: A simple text that denotes the software type that makes this distro
        self.software_packages_type = 'unknown'


class DistroPkgInfoLoader(object):

    '''
    Loads information from the distro installation tree into a DistroDef

    It will go through all package files
    '''

    def __init__(self, path):
        self.path = path

    def get_packages_info(self):
        '''
        This method will go throught each file, checking if it's a valid
        software package file by calling :method:`is_software_package` and
        calling :method:`load_package_info` if it's so.
        '''
        packages_info = set()
        # pylint: disable=I0011,W0612
        for dirpath, dirnames, filenames in os.walk(self.path):
            for filename in filenames:
                path = os.path.join(dirpath, filename)
                if self.is_software_package(path):
                    packages_info.add(self.get_package_info(path))

        # because we do not track of locations or how many copies of a given
        # package file exists in the installation tree, packages should be
        # comprised of unique entries
        return list(packages_info)

    def is_software_package(self, path):
        '''
        Determines if the given file at :param:`path` is a software package

        This check will be used to determine if :method:`load_package_info`
        will be called for file at :param:`path`. This method should be
        implemented by classes inheriting from :class:`DistroPkgInfoLoader` and
        could be as simple as checking for a file suffix.

        :param path: path to the software package file
        :type path: str
        :return: either True if the file is a valid software package or False
                 otherwise
        :rtype: bool
        '''
        raise NotImplementedError

    def get_package_info(self, path):
        '''
        Returns information about a given software package

        Should be implemented by classes inheriting from
        :class:`DistroDefinitionLoader`.

        :param path: path to the software package file
        :type path: str
        :returns: tuple with name, version, release, checksum and arch
        :rtype: tuple
        '''
        raise NotImplementedError


class DistroPkgInfoLoaderRpm(DistroPkgInfoLoader):

    '''
    Loads package information for RPM files
    '''

    def __init__(self, path):
        super(DistroPkgInfoLoaderRpm, self).__init__(path)
        try:
            os_dep.command('rpm')
            self.capable = True
        except ValueError:
            self.capable = False

    def is_software_package(self, path):
        '''
        Systems needs to be able to run the rpm binary in order to fetch
        information on package files. If the rpm binary is not available
        on this system, we simply ignore the rpm files found
        '''
        return self.capable and path.endswith('.rpm')

    def get_package_info(self, path):
        cmd = "rpm -qp --qf '%{NAME} %{VERSION} %{RELEASE} %{SIGMD5} %{ARCH}' "
        cmd += path
        info = utils.system_output(cmd, ignore_status=True)
        info = tuple(info.split(' '))
        return info


class DistroPkgInfoLoaderDeb(DistroPkgInfoLoader):

    '''
    Loads package information for DEB files
    '''

    def __init__(self, path):
        super(DistroPkgInfoLoaderDeb, self).__init__(path)
        try:
            os_dep.command('dpkg-deb')
            self.capable = True
        except ValueError:
            self.capable = False

    def is_software_package(self, path):
        return self.capable and (path.endswith('.deb') or
                                 path.endswith('.udeb'))

    def get_package_info(self, path):
        cmd = ("dpkg-deb --showformat '${Package} ${Version} ${Architecture}' "
               "--show ")
        cmd += path
        info = utils.system_output(cmd, ignore_status=True)
        name, version, arch = info.split(' ')
        return (name, version, '', '', arch)


#: the type of distro that will determine what loader will be used
DISTRO_PKG_INFO_LOADERS = {'rpm': DistroPkgInfoLoaderRpm,
                           'deb': DistroPkgInfoLoaderDeb}
