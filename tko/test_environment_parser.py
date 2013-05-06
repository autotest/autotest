import autotest.frontend.setup_django_environment
from autotest.frontend.afe import models

from autotest.tko.installed_software_parser import create_software_component_from_line

import django.core.exceptions


def get_unknown_distro():
    '''
    Gets the `unknown` distro

    If for some reason the distro is not found, we attempt to create it

    :returns: the special `unknown` distro
    :rtype: :class:`models.LinuxDistro`
    '''
    try:
        distro = models.LinuxDistro.objects.get(
            name__exact='unknown',
            major__exact=0,
            minor__exact=0,
            arch__exact='unknown')
    except django.core.exceptions.ObjectDoesNotExist:
        distro = models.LinuxDistro.objects.create(name='unknown',
                                                   major=0,
                                                   minor=0,
                                                   arch='unknown')
        distro.save()

    return distro


def parse_test_environment(path):
    '''
    Parses the test environment

    Currentt limtations:
    * the distro is set to the `unknown` distro because the distro detection
      on the client still needs some love.
    * limits the parsing of the test environment by looking at the installed
      software file

    :param path: the path to the installed software file
    :type path: string
    :returns: the numeric ID for the created (or found) test environment
    :rtype: integer
    '''
    distro = get_unknown_distro()

    scs = []
    for line in open(path).readlines():
        sc = create_software_component_from_line(line)
        scs.append(sc)

    te = None
    tes = models.TestEnvironment.objects.filter(distro=distro)
    if tes:
        for t in tes:
            t_scs = t.software_components.all()

            t_scs_ids = [obj.pk for obj in t_scs]
            t_scs_ids.sort()

            scs_ids = [obj.pk for obj in scs]
            scs_ids.sort()


            if t_scs_ids == scs_ids:
                te = t

    if te is None:
        te = models.TestEnvironment.objects.create(distro=distro)
        for sc in scs:
            te.software_components.add(sc)
        te.save()

    return te.pk
