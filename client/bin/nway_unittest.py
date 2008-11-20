#!/usr/bin/python

import unittest
import common
from autotest_lib.client.common_lib.test_utils import mock
from autotest_lib.client.bin import nway, job, cpuset


class TestNway(unittest.TestCase):
    def setUp(self):
        self.god = mock.mock_god()
        self.job = self.god.create_mock_class(job.job, "job")
        self.god.stub_function(cpuset, "my_available_exclusive_mem_nodes")
        nway.node_size = 100


    def tearDown(self):
        self.god.unstub_all()


    def test_run_twoway_pair(self):
        # setup
        total_cpus = 10
        mem_nodes = ['node1', 'node2', 'node3']
        total_nodes = len(mem_nodes)
        cpus = total_cpus  // 2
        node_cnt = total_nodes // 2
        repeats = 1
        test1 = "test1"
        test2 = "test2"
        tasks = []
        tasks.append([nway._constrained_test, self.job, test1, [], node_cnt,
                      range(cpus*0, cpus*1), test2, repeats])

        tasks.append([nway._constrained_test, self.job, test2, [], node_cnt,
                      range(cpus*1, cpus*2), test1, repeats])

        # record
        self.job.cpu_count.expect_call().and_return(total_cpus)
        ret = cpuset.my_available_exclusive_mem_nodes.expect_call()
        ret.and_return(mem_nodes)
        self.job.parallel.expect_call(*tasks)

        # run and check
        nway.run_twoway_pair(self.job, test1, test2, [], repeats)
        self.god.check_playback()


    def test_run_twoway_matrix(self):
        # setup
        total_cpus = 10
        mem_nodes = ['node1', 'node2', 'node3']
        total_nodes = len(mem_nodes)
        cpus = total_cpus  // 2
        node_cnt = total_nodes // 2
        mbytes = int( node_cnt * nway.node_size )
        self.god.stub_function(nway, "_twoway_test")
        self.god.stub_function(nway, "_oneway_test")

        benchmarks = ['bench1', 'bench2']
        antagonists = ['antag1', 'antag2']

        # record
        self.job.cpu_count.expect_call().and_return(total_cpus)
        ret = cpuset.my_available_exclusive_mem_nodes.expect_call()
        ret.and_return(mem_nodes)

        for test1 in benchmarks:
            for test2 in antagonists:
                nway._twoway_test.expect_call(self.job, test1, test2, [],
                                              node_cnt, cpus, 0)

        for test1 in benchmarks:
            nway._oneway_test.expect_call(self.job, test1, [], node_cnt,
                                          cpus, 0)

        # run and check
        nway.run_twoway_matrix(self.job, benchmarks, antagonists, [])
        self.god.check_playback()

if __name__ == "__main__":
    unittest.main()
