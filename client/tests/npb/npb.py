import os, shutil, logging, re
from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error

class npb(test.test):
    """
    This module runs the NAS Parallel Benchmarks on the client machine

    @note: Since we use gfortran to complie these benchmarks, this test might
            not be able to run on older Operating Systems.
    @see: http://www.nas.nasa.gov/Resources/Software/npb.html
    """
    version = 1
    def initialize(self, tests=''):
        # Initialize failure counter
        self.n_fail = 0
        # Get the parameters for run_once()
        self.tests = tests
        # Ratio is the reason between 1 and the number of CPUs of the system.
        self.ratio = 1.0 / utils.count_cpus()
        logging.debug('Ratio (1/n_cpus) found for this system: %s' % self.ratio)


    def setup(self, tarball='NPB3.3.tar.gz'):
        tarball = utils.unmap_url(self.bindir, tarball, self.tmpdir)
        utils.extract_tarball_to_dir(tarball, self.srcdir)
        os.chdir(self.srcdir)
        # Prepare the makefile and benchmarks to generate.
        utils.system('patch -p1 < ../enable-all-tests.patch')
        utils.system('cd NPB3.3-OMP && make suite')


    def run_once(self):
        """
        Run each benchmark twice, with different number of threads.

        A sanity check is made on each benchmark executed:
        The ratio between the times
        time_ratio = time_one_thrd / time_full_thrds

        Has to be contained inside an envelope:
        upper_bound = full_thrds * (1 + (1/n_cpus))
        lower_bound = full_thrds * (1 - (1/n_cpus))

        Otherwise, we throw an exception (this test might be running under a
        virtual machine and sanity check failure might mean bugs on smp
        implementation).
        """
        os.chdir(self.srcdir)

        # get the tests to run
        test_list = self.tests.split()

        if len(test_list) == 0:
            raise error.TestError('No tests (benchmarks) provided. Exit.')

        for itest in test_list:
            itest_cmd = os.path.join('NPB3.3-OMP/bin/', itest)
            try:
                itest = utils.run(itest_cmd)
            except:
                logging.error('NPB benchmark %s has failed. Output: %s',
                              itest_cmd, itest.stdout)
                self.n_fail += 1
            logging.debug(itest.stdout)

            # Get the number of threads that the test ran
            # (which is supposed to be equal to the number of system cores)
            m = re.search('Total threads\s*=\s*(.*)\n', itest.stdout)

            # Gather benchmark results
            ts = re.search('Time in seconds\s*=\s*(.*)\n', itest.stdout)
            mt = re.search('Mop/s total\s*=\s*(.*)\n', itest.stdout)
            mp = re.search('Mop/s/thread\s*=\s*(.*)\n', itest.stdout)

            time_seconds = float(ts.groups()[0])
            mops_total = float(mt.groups()[0])
            mops_per_thread = float(mp.groups()[0])

            logging.info('Test: %s', itest_cmd)
            logging.info('Time (s): %s', time_seconds)
            logging.info('Total operations executed (mops/s): %s', mops_total)
            logging.info('Total operations per thread (mops/s/thread): %s',
                          mops_per_thread)

            self.write_test_keyval({'test': itest_cmd})
            self.write_test_keyval({'time_seconds': time_seconds})
            self.write_test_keyval({'mops_total': mops_total})
            self.write_test_keyval({'mops_per_thread': mops_per_thread})

            # A little extra sanity check comes handy
            if int(m.groups()[0]) != utils.count_cpus():
                raise error.TestError("NPB test suite evaluated the number "
                                      "of threads incorrectly: System appears "
                                      "to have %s cores, but %s threads were "
                                      "executed.")

            # We will use this integer with float point vars later.
            full_thrds = float(m.groups()[0])

            # get duration for full_threads running.
            m = re.search('Time in seconds\s*=\s*(.*)\n', itest.stdout)
            time_full_thrds = float(m.groups()[0])

            # repeat the execution with single thread.
            itest_single_cmd = ''.join(['OMP_NUM_THREADS=1 ', itest_cmd])
            try:
                itest_single = utils.run(itest_single_cmd)
            except:
                logging.error('NPB benchmark single thread %s has failed. '
                              'Output: %s',
                              itest_single_cmd,
                              itest_single.stdout)
                self.n_fail += 1

            m = re.search('Time in seconds\s*=\s*(.*)\n', itest_single.stdout)
            time_one_thrd = float(m.groups()[0])

            # check durations
            ratio = self.ratio
            time_ratio = float(time_one_thrd / time_full_thrds)
            upper_bound = full_thrds * (1 + ratio)
            lower_bound = full_thrds * (1 - ratio)
            logging.debug('Time ratio for %s: %s', itest_cmd, time_ratio)
            logging.debug('Upper bound: %s', upper_bound)
            logging.debug('Lower bound: %s', lower_bound)

            violates_upper_bound = time_ratio > upper_bound
            violates_lower_bound = time_ratio < lower_bound
            if violates_upper_bound or violates_lower_bound:
                logging.error('NPB benchmark %s failed sanity check '
                              '- time ratio outside bounds' % itest_cmd)
                self.n_fail += 1
            else:
                logging.debug('NPB benchmark %s sanity check PASS' % itest_cmd)


    def cleanup(self):
        """
        Raise TestError if failures were detected during test execution.
        """
        if self.n_fail != 0:
            raise error.TestError('NPB test failed.')
        else:
            logging.info('NPB test passed.')
