#!/usr/bin/python

import unittest
import common
from autotest_lib.client.common_lib import profiler_manager


# simple job stub for using in tests
class stub_job(object):
    tmpdir = "/home/autotest/tmp"
    autodir = "/home/autotest"


# simple profiler stub for using in tests
class stub_profiler(object):
    started = 0
    def __init__(self, name):
        self.name = name
    @classmethod
    def start(cls, test):
        cls.started += 1
    @classmethod
    def stop(cls, test):
        cls.started -= 1


# replace profiler_manager.load_profiler with a simple stub
class stub_manager(profiler_manager.profiler_manager):
    def load_profiler(self, profiler, args, dargs):
        return stub_profiler(profiler)


class TestProfilerManager(unittest.TestCase):
    def test_starts_with_no_profilers(self):
        p = stub_manager(stub_job)
        self.assertEqual(set(), p.current_profilers())


    def test_single_add(self):
        p = stub_manager(stub_job)
        p.add("prof1")
        self.assertEqual(set(["prof1"]), p.current_profilers())


    def test_duplicate_adds(self):
        p = stub_manager(stub_job)
        p.add("prof1")
        p.add("prof1")
        self.assertEqual(set(["prof1"]), p.current_profilers())


    def test_multiple_adds(self):
        p = stub_manager(stub_job)
        p.add("prof1")
        p.add("prof2")
        self.assertEqual(set(["prof1", "prof2"]), p.current_profilers())


    def test_add_and_delete(self):
        p = stub_manager(stub_job)
        p.add("prof1")
        p.add("prof2")
        p.delete("prof1")
        self.assertEqual(set(["prof2"]), p.current_profilers())


    def test_present_with_no_profilers(self):
        p = stub_manager(stub_job)
        self.assertEqual(False, p.present())


    def test_present_after_add(self):
        p = stub_manager(stub_job)
        p.add("prof1")
        self.assertEqual(True, p.present())


    def test_present_after_add_and_remove(self):
        p = stub_manager(stub_job)
        p.add("prof1")
        p.delete("prof1")
        self.assertEqual(False, p.present())


    def test_started(self):
        p = stub_manager(stub_job)
        p.add("prof1")
        p.add("prof2")
        started = stub_profiler.started
        self.assertEqual(False, p.active())
        p.start(object())
        self.assertEqual(started + 2, stub_profiler.started)
        self.assertEqual(True, p.active())


    def test_stop(self):
        p = stub_manager(stub_job)
        p.add("prof1")
        p.add("prof2")
        started = stub_profiler.started
        self.assertEqual(False, p.active())
        test = object()
        p.start(test)
        p.stop(test)
        self.assertEqual(started, stub_profiler.started)
        self.assertEqual(False, p.active())



if __name__ == "__main__":
    unittest.main()
