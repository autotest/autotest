"""The standalone harness interface

The default interface as required for the standalone reboot helper.
"""

__author__ = """Copyright Andy Whitcroft 2007"""

import logging
import os
import shutil

from autotest.client import utils
from autotest.client.shared import error, distro
from autotest.client.shared.settings import settings

import harness


class harness_standalone(harness.harness):

    """The standalone server harness

    Properties:
            job
                    The job object for this job
    """

    def __init__(self, job, harness_args):
        """
                job
                        The job object for this job
        """
        self.autodir = os.path.abspath(os.environ['AUTODIR'])
        self.setup(job)

        tmpdir = os.path.join(self.autodir, 'tmp')
        tests_dir = settings.get_value('COMMON', 'test_output_dir',
                                       default=tmpdir)

        src = job.control_get()
        dest = os.path.join(tests_dir, 'control')
        if os.path.abspath(src) != os.path.abspath(dest):
            shutil.copyfile(src, dest)
            job.control_set(dest)

        def yield_default_initlevel():
            """
            If we really can't figure out something better, default to '2',
            which is the case with some debian systems
            """
            init_default = '2'
            logging.error('Could not determine initlevel, assuming %s' %
                          init_default)
            return init_default

        rc = os.path.join(self.autodir, 'tools/autotest')
        # see if system supports event.d versus systemd versus inittab
        supports_eventd = os.path.exists('/etc/event.d')
        supports_systemd = os.path.exists('/etc/systemd')
        supports_inittab = os.path.exists('/etc/inittab')
        # This is the best heuristics I can think of for identifying
        # an embedded system running busybox
        busybox_system = (os.readlink('/bin/sh') == 'busybox')

        # Small busybox systems usually use /etc/rc.d/ straight
        if busybox_system:
            initdefault = ''

        elif supports_eventd or supports_systemd:
            try:
                # NB: assuming current runlevel is default
                cmd_result = utils.run('/sbin/runlevel', verbose=False)
                initdefault = cmd_result.stdout.split()[1]
            except (error.CmdError, IndexError):
                initdefault = yield_default_initlevel()

        elif supports_inittab:
            try:
                cmd_result = utils.run('grep :initdefault: /etc/inittab',
                                       verbose=False)
                initdefault = cmd_result.stdout.split(':')[1]
            except (error.CmdError, IndexError):
                initdefault = yield_default_initlevel()

        else:
            initdefault = yield_default_initlevel()

        vendor = distro.detect().name
        service = '/etc/init.d/autotest'
        if vendor == 'SUSE':
            service_link = '/etc/init.d/rc%s.d/S99autotest' % initdefault
        else:
            service_link = '/etc/rc%s.d/S99autotest' % initdefault
        try:
            if os.path.islink(service):
                os.remove(service)
            if os.path.islink(service_link):
                os.remove(service_link)
            os.symlink(rc, service)
            os.symlink(rc, service_link)
        except (OSError, IOError):
            logging.info("Could not symlink init scripts (lack of permissions)")
