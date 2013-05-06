'''
The general format for each line of the installed-software file is:

kind name version release checksum arch
'''

import autotest.frontend.setup_django_environment
from autotest.frontend.afe import models

import django.core.exceptions


def create_kind(name):
    '''
    Creates a new kind being silent if it already exists

    :param name: name that describes the software kind
    :type name: str
    :return: the object object found or the newly created one
    :rtype: :class:`models.SoftwareKind`
    '''
    try:
        kind = models.SoftwareComponentKind.objects.get(name__exact=name)
    except django.core.exceptions.ObjectDoesNotExist:
        kind = models.SoftwareComponentKind.objects.create(name=name)
    return kind


def create_arch(name):
    '''
    Creates a new arch being silent if it already exists

    :param name: name that describes the software arch
    :type name: str
    :return: the object object found or the newly created one
    :rtype: :class:`models.SoftwareArch`
    '''
    try:
        arch = models.SoftwareComponentArch.objects.get(name__exact=name)
    except django.core.exceptions.ObjectDoesNotExist:
        arch = models.SoftwareComponentArch.objects.create(name=name)
    return arch


def create_software_component(kind, name, version, release, checksum, arch):
    '''
    Creates a new software component being silent if it already exists

    :param kind: the kind of the software component installed
    :type kind: :class:`models.SoftwareKind`
    :param name: name that describes the software component
    :type name: str
    :param version: complete version number (minus the release part). This will
                    be mapped to :attr:`models.SoftwareComponent.version`
    :type version: str
    :param release: release number, usually extra version information. It will
                    be mapped to :attr:`models.SoftwareComponent.version`
    :type release: str
    :param checksum: a hash that uniquely identifies this software component.
                     Maps to :attr:`models.SoftwareComponent.version`
    :type checksum: str
    :param arch: the arch of the software component installed
    :type arch: :class:`models.SoftwareArch`
    :return: the object object found or the newly created one
    :rtype: :class:`models.SoftwareComponent`
    '''
    try:
        sc = models.SoftwareComponent.objects.get(
            kind__name__exact=kind,
            name__exact=name,
            version__exact=version,
            release__exact=release,
            checksum__exact=checksum,
            arch__name__exact=arch)
    except django.core.exceptions.ObjectDoesNotExist:
        sc = models.SoftwareComponent.objects.create(kind=create_kind(kind),
                                                     name=name,
                                                     version=version,
                                                     release=release,
                                                     checksum=checksum,
                                                     arch=create_arch(arch))
    return sc


def create_software_component_from_line(line):
    '''
    Utility method that creates :class:`models.SoftwareComponents`

    The format of line of text supplied must be:

    `kind name version release checksum arch`

    :param path: path to a text file that conforms to the format described
                 above.
    :type path: str
    '''
    kind, name, version, release, checksum, arch = line.split()
    return create_software_component(kind, name, version, release, checksum, arch)


def parse_file(path):
    '''
    Utility method that creates :class:`models.SoftwareComponents` from a file

    The format of the lines MUST conform to the format described on
    :func:create_software_component_from_line documentation.

    :param path: path to a text file that conforms to the format described
                 above.
    :type path: str
    '''
    for line in open(path).readlines():
        create_software_component_from_line(line)
