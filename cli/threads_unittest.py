#!/usr/bin/python
#
# Copyright 2008 Google Inc. All Rights Reserved.

"""Tests for thread."""

import unittest, sys, os

import threading, Queue

import common
from autotest_lib.cli import cli_mock, threads


class thread_unittest(cli_mock.cli_unittest):
    results = Queue.Queue()

    def _workload(self, i):
        self.results.put(i*i)


    def test_starting(self):
        self.god.stub_class_method(threading.Thread, 'start')
        threading.Thread.start.expect_call().and_return(None)
        threading.Thread.start.expect_call().and_return(None)
        threading.Thread.start.expect_call().and_return(None)
        threading.Thread.start.expect_call().and_return(None)
        threading.Thread.start.expect_call().and_return(None)
        th = threads.ThreadPool(self._workload, numthreads=5)
        self.god.check_playback()


    def test_one_thread(self):
        th = threads.ThreadPool(self._workload, numthreads=1)
        th.queue_work(range(10))
        th.wait()
        res = []
        while not self.results.empty():
            res.append(self.results.get())
        self.assertEqualNoOrder([0, 1, 4, 9, 16, 25, 36, 49, 64, 81], res)


    def _threading(self, numthreads, count):
        th = threads.ThreadPool(self._workload, numthreads=numthreads)
        th.queue_work(range(count))
        th.wait()
        res = []
        while not self.results.empty():
            res.append(self.results.get())
        self.assertEqualNoOrder([i*i for i in xrange(count)], res)


    def test_threading(self):
        self._threading(10, 10)


    def test_threading_lots(self):
        self._threading(100, 100)


    def test_threading_multi_queueing(self):
        th = threads.ThreadPool(self._workload, numthreads=5)
        th.queue_work(range(5))
        th.queue_work(range(5, 10))
        th.wait()
        res = []
        while not self.results.empty():
            res.append(self.results.get())
        self.assertEqualNoOrder([i*i for i in xrange(10)], res)


if __name__ == '__main__':
    unittest.main()
