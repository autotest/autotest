import os, sys, subprocess, logging
from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error


class disktest(test.test):
    """
    Autotest module for disktest.

    Pattern test of the disk, using unique signatures for each block and each
    iteration of the test. Designed to check for data corruption issues in the
    disk and disk controller.

    It writes 50MB/s of 500KB size ops.

    @author: Martin Bligh (mbligh@google.com)
    """
    version = 2
    preserve_srcdir = True

    def setup(self):
        """
        Compiles disktest.
        """
        os.chdir(self.srcdir)
        utils.make('clean')
        utils.make()


    def initialize(self):
        """
        Verifies if we have gcc to compile disktest.
        """
        self.job.require_gcc()


    def test_one_disk_chunk(self, disk, chunk):
        """
        Tests one part of the disk by spawning a disktest instance.

        @param disk: Directory (usually a mountpoint).
        @param chunk: Portion of the disk used.
        """
        logging.info("Testing %d MB files on %s in %d MB memory, chunk %s",
                     self.chunk_mb, disk, self.memory_mb, chunk)
        cmd = ("%s/disktest -m %d -f %s/testfile.%d -i -S" %
               (self.srcdir, self.chunk_mb, disk, chunk))
        logging.debug("Running '%s'", cmd)
        p = subprocess.Popen(cmd, shell=True)
        return(p.pid)


    def run_once(self, disks=None, gigabytes=None, chunk_mb=None):
        """
        Runs one iteration of disktest.

        @param disks: List of directories (usually mountpoints) to be passed
                to the test.
        @param gigabytes: Disk space that will be used for the test to run.
        @param chunk_mb: Size of the portion of the disk used to run the test.
                Cannot be larger than the total amount of free RAM.
        """
        os.chdir(self.srcdir)
        if chunk_mb is None:
            chunk_mb = utils.memtotal() / 1024
        if disks is None:
            disks = [self.tmpdir]
        if gigabytes is None:
            free = 100 # cap it at 100GB by default
            for disk in disks:
                free = min(utils.freespace(disk) / 1024**3, free)
            gigabytes = free
            logging.info("Resizing to %s GB", gigabytes)
            sys.stdout.flush()

        self.chunk_mb = chunk_mb
        self.memory_mb = utils.memtotal()/1024
        if self.memory_mb > chunk_mb:
            raise error.TestError("Too much RAM (%dMB) for this test to work" %
                                  self.memory_mb)

        chunks = (1024 * gigabytes) / chunk_mb

        logging.info("Total of disk chunks that will be used: %s", chunks)
        for i in range(chunks):
            pids = []
            for disk in disks:
                pid = self.test_one_disk_chunk(disk, i)
                pids.append(pid)
            errors = []
            for pid in pids:
                (junk, retval) = os.waitpid(pid, 0)
                if (retval != 0):
                    errors.append(retval)
            if errors:
                raise error.TestError("Errors from children: %s" % errors)
