import os, time, re, subprocess, shutil, logging
from autotest_lib.client.bin import utils, test
from autotest_lib.client.common_lib import error


class dma_memtest(test.test):
    """
    A test for the memory subsystem against heavy IO and DMA operations,
    implemented based on the work of Doug Leford
    (http://people.redhat.com/dledford/memtest.shtml)

        @author Lucas Meneghel Rodrigues (lucasmr@br.ibm.com)
        @author Rodrigo Sampaio Vaz (rsampaio@br.ibm.com)
    """
    version = 1
    def initialize(self):
        self.cachedir = os.path.join(self.bindir, 'cache')
        self.nfail = 0


    def setup(self, tarball_base='linux-2.6.18.tar.bz2', parallel=True):
        """
        Downloads a copy of the linux kernel, calculate an estimated size of
        the uncompressed tarball, use this value to calculate the number of
        copies of the linux kernel that will be uncompressed.

            @param tarball_base: Name of the kernel tarball location that will
            be looked up on the kernel.org mirrors.
            @param parallel: If we are going to uncompress the copies of the
            kernel in parallel or not
        """
        if not os.path.isdir(self.cachedir):
            os.makedirs(self.cachedir)
        self.parallel = parallel

        kernel_repo = 'http://www.kernel.org/pub/linux/kernel/v2.6'
        tarball_url = os.path.join(kernel_repo, tarball_base)
        tarball_md5 = '296a6d150d260144639c3664d127d174'
        logging.info('Downloading linux kernel tarball')
        self.tarball = utils.unmap_url_cache(self.cachedir, tarball_url,
                                             tarball_md5)
        size_tarball = os.path.getsize(self.tarball) / 1024 / 1024
        # Estimation of the tarball size after uncompression
        compress_ratio = 5
        est_size = size_tarball * compress_ratio
        self.sim_cps = self.get_sim_cps(est_size)
        logging.info('Source file: %s' % tarball_base)
        logging.info('Megabytes per copy: %s' % size_tarball)
        logging.info('Compress ratio: %s' % compress_ratio)
        logging.info('Estimated size after uncompression: %s' % est_size)
        logging.info('Number of copies: %s' % self.sim_cps)
        logging.info('Parallel: %s' % parallel)


    def get_sim_cps(self, est_size):
        '''
        Calculate the amount of simultaneous copies that can be uncompressed
        so that it will make the system swap.

            @param est_size: Estimated size of uncompressed linux tarball
        '''
        mem_str = utils.system_output('grep MemTotal /proc/meminfo')
        mem = int(re.search(r'\d+', mem_str).group(0))
        mem = int(mem / 1024)

        # The general idea here is that we'll make an amount of copies of the
        # kernel tree equal to 1.5 times the physical RAM, to make sure the
        # system swaps, therefore reading and writing stuff to the disk. The
        # DMA reads and writes together with the memory operations that will
        # make it more likely to reveal failures in the memory subsystem.
        sim_cps = (1.5 * mem) / est_size

        if (mem % est_size) >= (est_size / 2):
            sim_cps += 1

        if (mem / 32) < 1:
            sim_cps += 1

        return int(sim_cps)


    def run_once(self):
        """
        Represents a single iteration of the process. Uncompresses a previously
        calculated number of copies of the linux kernel, sequentially or in
        parallel, and then compares the tree with a base tree, that was
        uncompressed on the very beginning.
        """

        parallel_procs = []

        os.chdir(self.tmpdir)
        # This is the reference copy of the linux tarball
        # that will be used for subsequent comparisons
        logging.info('Unpacking base copy')
        base_dir = os.path.join(self.tmpdir, 'linux.orig')
        utils.extract_tarball_to_dir(self.tarball, base_dir)
        logging.info('Unpacking test copies')
        for j in range(self.sim_cps):
            tmp_dir = 'linux.%s' % j
            if self.parallel:
                os.mkdir(tmp_dir)
                # Start parallel process
                tar_cmd = ['tar', 'jxf', self.tarball, '-C', tmp_dir]
                logging.debug("Unpacking tarball to %s", tmp_dir)
                parallel_procs.append(subprocess.Popen(tar_cmd,
                                                       stdout=subprocess.PIPE,
                                                       stderr=subprocess.PIPE))
            else:
                logging.debug("Unpacking tarball to %s", tmp_dir)
                utils.extract_tarball_to_dir(self.tarball, tmp_dir)
        # Wait for the subprocess before comparison
        if self.parallel:
            logging.debug("Wait background processes before proceed")
            for proc in parallel_procs:
                proc.wait()

        parallel_procs = []

        logging.info('Comparing test copies with base copy')
        for j in range(self.sim_cps):
            tmp_dir = 'linux.%s/%s' % (j,
                            os.path.basename(self.tarball).strip('.tar.bz2'))
            if self.parallel:
                diff_cmd = ['diff', '-U3', '-rN', 'linux.orig', tmp_dir]
                logging.debug("Comparing linux.orig with %s", tmp_dir)
                p = subprocess.Popen(diff_cmd,
                                     stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE)
                parallel_procs.append(p)
            else:
                try:
                    logging.debug('Comparing linux.orig with %s', tmp_dir)
                    utils.system('diff -U3 -rN linux.orig linux.%s' % j)
                except error.CmdError, e:
                    self.nfail += 1
                    logging.error('Error comparing trees: %s', e)

        for proc in parallel_procs:
            out_buf = proc.stdout.read()
            out_buf += proc.stderr.read()
            proc.wait()
            if out_buf != "":
                self.nfail += 1
                logging.error('Error comparing trees: %s', out_buf)

        # Clean up for the next iteration
        parallel_procs = []

        logging.info('Cleaning up')
        for j in range(self.sim_cps):
            tmp_dir = 'linux.%s' % j
            shutil.rmtree(tmp_dir)
        shutil.rmtree(base_dir)


    def cleanup(self):
        if self.nfail != 0:
            raise error.TestError('DMA memory test failed.')
        else:
            logging.info('DMA memory test passed.')
