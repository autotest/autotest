"""The standalone harness interface

The default interface as required for the standalone reboot helper.
"""

__author__ = """Copyright Andy Whitcroft 2007"""

from autotest_lib.client.common_lib import utils, error
import os, harness, shutil, logging

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

        src = job.control_get()
        dest = os.path.join(self.autodir, 'control')
        if os.path.abspath(src) != os.path.abspath(dest):
            shutil.copyfile(src, dest)
            job.control_set(dest)

        logging.info('Symlinking init scripts')
        rc = os.path.join(self.autodir, 'tools/autotest')
        # see if system supports event.d versus systemd versus inittab
        supports_eventd = os.path.exists('/etc/event.d')
        supports_systemd = os.path.exists('/etc/systemd')
        supports_inittab = os.path.exists('/etc/inittab')
        if supports_eventd or supports_systemd:
            # NB: assuming current runlevel is default
            initdefault = utils.system_output('/sbin/runlevel').split()[1]
        elif supports_inittab:
            initdefault = utils.system_output('grep :initdefault: /etc/inittab')
            initdefault = initdefault.split(':')[1]
        else:
            initdefault = '2'

        try:
            utils.system('ln -sf %s /etc/init.d/autotest' % rc)
            utils.system('ln -sf %s /etc/rc%s.d/S99autotest' % (rc,initdefault))
        except:
            logging.warning("Linking init scripts failed")
