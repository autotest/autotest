# Will need some libaries to compile. Do 'apt-get build-dep oprofile'
import os, shutil
from autotest_lib.client.bin import autotest_utils, profiler
from autotest_lib.client.common_lib import utils

class oprofile(profiler.profiler):
    version = 5

# Notes on whether to use the local copy or the builtin from source:
# local = None
#      Try to use source copy if it works, else use local
# local = False
#       Force use of the source copy
# local = True
#       Force use of the local copy

# http://prdownloads.sourceforge.net/oprofile/oprofile-0.9.3.tar.gz
    def setup(self, tarball = 'oprofile-0.9.3.tar.bz2', local = None,
                                                            *args, **dargs):
        if local == True:
            return

        try:
            self.tarball = utils.unmap_url(self.bindir, tarball,
                                                    self.tmpdir)
            autotest_utils.extract_tarball_to_dir(self.tarball, self.srcdir)
            os.chdir(self.srcdir)

            patch = os.path.join(self.bindir,"oprofile-69455.patch")
            utils.system('patch -p1 < %s' % patch)
            utils.system('./configure --with-kernel-support --prefix=' + \
                                                    self.srcdir)
            utils.system('make')
            utils.system('make install')
        except:
            # Build from source failed.
            # But maybe can still use the local copy
            local_opcontrol = os.path.exists('/usr/bin/opcontrol')
            local_opreport = os.path.exists('/usr/bin/opreport')
            if local == False or not local_opcontrol or not local_opreport:
                raise


    def initialize(self, vmlinux = None, events = [], others = None,
                                                            local = None):
        if not vmlinux:
            self.vmlinux = autotest_utils.get_vmlinux()
        else:
            self.vmlinux = vmlinux
        if not len(events):
            self.events = ['default']
        else:
            self.events = events
        self.others = others

        # If there is existing setup file, oprofile may fail to start with default parameters.
        if os.path.isfile('/root/.oprofile/daemonrc'):
            os.rename('/root/.oprofile/daemonrc', '/root/.oprofile/daemonrc.org')

        setup = ' --setup'
        if not self.vmlinux:
            setup += ' --no-vmlinux'
        else:
            setup += ' --vmlinux=%s' % self.vmlinux
        for e in self.events:
            setup += ' --event=%s' % e
        if self.others:
            setup += ' ' + self.others

        src_opreport  = os.path.join(self.srcdir, '/bin/opreport')
        src_opcontrol = os.path.join(self.srcdir, '/bin/opcontrol')
        if local == False or (local == None and
                                os.path.exists(src_opreport) and
                                os.path.exists(src_opcontrol)):
            print "Using source-built copy of oprofile"
            self.opreport = src_opreport
            self.opcontrol = src_opcontrol
        else:
            print "Using machine local copy of oprofile"
            self.opreport = '/usr/bin/opreport'
            self.opcontrol = '/usr/bin/opcontrol'

        utils.system(self.opcontrol + setup)


    def start(self, test):
        utils.system(self.opcontrol + ' --shutdown')
        utils.system(self.opcontrol + ' --reset')
        utils.system(self.opcontrol + ' --start')


    def stop(self, test):
        utils.system(self.opcontrol + ' --stop')
        utils.system(self.opcontrol + ' --dump')


    def report(self, test):
        # Output kernel per-symbol profile report
        reportfile = test.profdir + '/oprofile.kernel'
        if self.vmlinux:
            report = self.opreport + ' -l ' + self.vmlinux
            if os.path.exists(autotest_utils.get_modules_dir()):
                report += ' -p ' + autotest_utils.get_modules_dir()
            utils.system(report + ' > ' + reportfile)
        else:
            utils.system("echo 'no vmlinux found.' > %s" % reportfile)

        # output profile summary report
        reportfile = test.profdir + '/oprofile.user'
        utils.system(self.opreport + ' --long-filenames ' + ' > ' + reportfile)

        utils.system(self.opcontrol + ' --shutdown')
