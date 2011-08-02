import os, string, logging, re, random, shutil
from autotest_lib.client.bin import test, os_dep, utils
from autotest_lib.client.common_lib import error


def find_mnt_pt(path):
    """
    Find on which mount point a given path is mounted.

    @param path: Path we want to figure its mount point.
    """
    pth = os.path.abspath(path)
    while not os.path.ismount(pth):
        pth = os.path.dirname(pth)
    return pth


class ffsb(test.test):
    """
    This class wraps FFSB (Flexible File System Benchmark) execution
    under autotest.

    @author Onkar N Mahajan (onkar.n.mahajan@linux.vnet.ibm.com)
    """
    version = 1
    params = {}
    tempdirs = []
    bytes = {'K':1024 , 'k':1024,
             'M':1048576, 'm':1048576,
             'G':1073741824, 'g':1073741824,
             'T':1099511627776 , 't':1099511627776}


    def initialize(self):
        self.job.require_gcc()
        self.results = []
        self.nfail = 0


    def set_ffsb_params(self, usrfl):
        """
        This function checks for the user supplied FFSB profile file
        and validates it against the availble resources on the
        guest - currently only disk space validation is supported
        but adjusting the number of threads according to the vcpus
        exported by the qemu-kvm also needs to be added.

        @param usrfl: Path to the user profile file.
        """
        d = {}
        fr = open(usrfl,'r')
        for line in fr.read().split('\n'):
            p = re.compile(r'\s*\t*\[{1}filesystem(\d+)\]{1}')
            m = p.match(line)
            if m:
                fsno = int(line[m.start(1):m.end(1)])
                d[fsno] = []
            p = re.compile(r'(\s*\t*location)\=(.*)')
            m = p.match(line)
            if m:
                path = line[m.start(2):m.end(2)]
                mntpt = find_mnt_pt(path)
                f = os.statvfs(mntpt)
                avl_dsk_spc = f.f_bfree * f.f_bsize
                avl_dsk_spc *= 0.95
                d[fsno].append(mntpt)
                d[fsno].append(int(avl_dsk_spc))
            p = re.compile(r'(\s*\t*num_files)\=(\d+)')

            m = p.match(line)
            if m:
                usrnumfl = int(line[m.start(2):m.end(2)])
                d[fsno].append(usrnumfl)
            p = re.compile(r'(\s*\t*max_filesize)\=(\d+[kKMmGgTt]?)')
            m = p.match(line)
            if m:
                usrmaxflsz = line[m.start(2):m.end(2)]
                usrmaxflsz = int(usrmaxflsz[0:-1]) * self.bytes[usrmaxflsz[-1]]
                d[fsno].append(usrmaxflsz)
        for k in d.keys():
            while d[k][2]*d[k][3] >= d[k][1]:
                d[k][2] -= 1
            if d[k][2] == 0:
                d[k][2] = 1
                d[k][3] = d[k][1]
            # If the ffsb mount point is on the same file system
            # then use the available disk space after the previous
            # tests
            for k1 in d.keys():
                if d[k1][0] == d[k][0]:
                    d[k1][1] -= (d[k][2]*d[k][3])
        fr.close()
        return d


    def dup_ffsb_profilefl(self):
        """
        Validates the path from the FFSB configuration file, the
        disk space available for the test, warn the user and
        change the file sizes and/or number of files to be used for
        generating the workload according to the available disk space
        on the guest.
        """
        self.usrfl = '%s/%s' % (os.path.split(self.srcdir)[0],'profile.cfg')
        self.sysfl = '%s/%s' % (self.srcdir,'profile.cfg')

        params = self.set_ffsb_params(self.usrfl)

        fsno = 0
        fr = open(self.usrfl,'r')
        fw = open(self.sysfl,'w')
        for line in fr.read().split('\n'):
            p = re.compile(r'\s*\t*\[{1}filesystem(\d+)\]{1}')
            m = p.match(line)
            if m:
                fsno = int(line[m.start(1):m.end(1)])
            p = re.compile(r'(\s*\t*location)\=(.*)')
            m = p.match(line)
            if m:
                while True:
                    dirnm = ''.join(random.choice(string.letters) for i in xrange(9))
                    if line[m.end(2) - 1] == '/':
                        newline = '%s%s' % (line[0:m.end(2)], dirnm)
                        ffsbdir = '%s%s' % (line[m.start(2):m.end(2)], dirnm)
                    else:
                        newline = '%s/%s' % (line[0:m.end(2)], dirnm)
                        ffsbdir = '%s/%s' % (line[m.start(2):m.end(2)], dirnm)
                    self.tempdirs.append(ffsbdir)
                    if os.path.exists(ffsbdir):
                        continue
                    else:
                        os.makedirs(ffsbdir)
                        break
                fw.write(newline+'\n')
                continue
            p = re.compile(r'(\s*\t*num_files)\=(.*)')
            m = p.match(line)
            if m:
                newline = '%s=%s' % (line[0:m.end(1)], str(params[fsno][2]))
                fw.write(newline+'\n')
                continue
            p = re.compile(r'(\s*\t*max_filesize)\=(\d+[kKMmGgTt]?)')
            m = p.match(line)
            if m:
                newline = '%s%s' % (line[0:m.start(2)], str(params[fsno][3]))
                fw.write(newline+'\n')
                continue
            fw.write(line+'\n')
        fr.close()
        fw.close()


    def setup(self, tarball='ffsb-6.0-rc2.tar.bz2'):
        """
        Uncompress the FFSB tarball and compiles it.

        @param tarball: FFSB tarball. Could be either a path relative to
                self.srcdir or a URL.
        """
        tarball = utils.unmap_url(self.bindir, tarball, self.tmpdir)
        utils.extract_tarball_to_dir(tarball, self.srcdir)
        os.chdir(self.srcdir)
        os_dep.command('gcc')
        utils.configure()
        utils.make()


    def run_once(self):
        """
        Runs a single iteration of the FFSB.
        """
        self.dup_ffsb_profilefl()
        # Run FFSB using abspath
        cmd = '%s/ffsb %s/profile.cfg' % (self.srcdir, self.srcdir)
        logging.info("FFSB command: %s", cmd)
        self.results_path = os.path.join(self.resultsdir,
                                         'raw_output_%s' % self.iteration)
        try:
            self.results = utils.system_output(cmd, retain_output=True)
            logging.info(self.results)
            utils.open_write_close(self.results_path, self.results)
        except error.CmdError, e:
            self.nfail += 1
            logging.error('Failed to execute FFSB : %s', e)


    def postprocess(self):
        """
        Do test postprocessing. Fail the test or clean up results.
        """
        if self.nfail != 0:
            raise error.TestError('FFSB test failed.')
        else:
            logging.info('FFSB test passed')
            logging.info('Cleaning up test data...')
            for l in self.tempdirs:
                shutil.rmtree(l)
