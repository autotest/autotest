import os, time
from autotest_lib.client.bin import test, autotest_utils, cpuset
from autotest_lib.client.common_lib import utils, error


class shrink_slab(test.test):
    version = 1

    def dirty_slab(self):
        # Dirty some slab
        for i in range(1, 20000):
            utils.system('echo ACCD > %d' % i)


    def mem_pressure(self):
        # Generate memory pressure to get the slab reclaimed
        utils.system('dd if=/dev/hdc3 of=tmp bs=1M count=1024 &> /dev/null')


    def slab_usage(self):
        slab_used = 0
        for n in cpuset.my_mem_nodes():
            slab_used += int(utils.system_output(
              'cat /sys/devices/system/node/node%d/meminfo | '
              'awk \'/Slab:/ {print $4}\'' % n))
        return slab_used


    def test1(self):
        # Check that slab is reclaimed from the current container when there is
        # memory pressure.
        autotest_utils.drop_caches()
        utils.system('rm -rf %s/*' % self.tmpdir)
        os.chdir(self.tmpdir)

        start_slab = self.slab_usage()
        print 'Starting slab: %d' % start_slab
        self.dirty_slab()
        mid_slab = self.slab_usage()
        print 'Slab after polluting: %d' % mid_slab

        self.mem_pressure()
        end_slab = self.slab_usage()
        print 'Slab after reclaim: %d' % end_slab

        if mid_slab - start_slab < 10000:
            raise error.TestFail('Not enough slab polluted as expected')
        if mid_slab - end_slab < 5000:
            raise error.TestFail(
                'Not enough slab reclaimed. This might be a test failure')
        print 'Test 1 PASSED'


    def test2(self):
        # Check that slab is not reclaimed from the main container when there is
        # memory pressure in another container.
        autotest_utils.drop_caches()
        utils.system('rm -rf %s/*' % self.tmpdir)
        os.chdir(self.tmpdir)

        start_slab = self.slab_usage()
        print 'Starting slab: %d' % start_slab
        self.dirty_slab()
        mid_slab = self.slab_usage()
        print 'Slab after polluting: %d' % mid_slab

        container = cpuset.cpuset('dd_container', job_size=100,
                                  job_pid=os.getpid(), cpus=[0,1,2,3], root='')
        self.mem_pressure()
        container.release()
        end_slab = self.slab_usage()
        print 'Slab after reclaim: %d' % end_slab

        if mid_slab - start_slab < 10000:
            raise error.TestFail('Not enough slab polluted as expected')
        if mid_slab - end_slab > 2000:
            raise error.TestFail(
                'Seems like slab was reclaimed from other container. '
                'This might be a test failure')
        print 'Test 2 PASSED'


    def execute(self):
        self.test1()
        self.test2()
