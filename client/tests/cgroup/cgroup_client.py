#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Interactive python script for testing cgroups. It will try to use system
resources such as cpu, memory and device IO. The other cgroups test
instrumentation will inspect whether the linux box behaved as it should.

@copyright: 2011 Red Hat Inc.
@author: Lukas Doktor <ldoktor@redhat.com>
"""
import array, sys, time, math, os
from tempfile import mktemp

def test_smoke(args):
    """
    SIGSTOP the process and after SIGCONT exits.
    """
    print "TEST: smoke"
    print "TEST: wait for input"
    raw_input()
    print "PASS: smoke"


def test_memfill(args):
    """
    SIGSTOP and after SIGCONT fills the memory up to size size.
    """
    size = 1024
    f = sys.stdout
    if args:
        size = int(args[0])
        if len(args) > 1:
            f = open(args[1], 'w', 0)
    print "TEST: memfill (%dM)" % size
    print "Redirecting to: %s" % f.name
    f.write("TEST: memfill (%dM)\n" % size)
    f.write("TEST: wait for input\n")
    raw_input()
    mem = array.array('B')
    buf = ""
    for i in range(1024 * 1024):
        buf += '\x00'
    for i in range(size):
        mem.fromstring(buf)
        f.write("TEST: %dM\n" % i)
        try:
            f.flush()
            os.fsync(f)
        except:
            pass
    f.write("PASS: memfill (%dM)\n" % size)


def test_cpu(args):
    """
    Stress the CPU.
    """
    print "TEST: cpu"
    print "TEST: wait for input"
    raw_input()
    while True:
        for i in range (1000, 10000):
            math.factorial(i)


def test_devices(args):
    if args:
        if args[0] == "write":
            test_devices_write()
        else:
            test_devices_read()
    else:
        test_devices_read()


def test_devices_read():
    """
    Inf read from /dev/zero
    """
    print "TEST: devices read"
    print "TEST: wait for input"
    raw_input()

    dev = open("/dev/zero", 'r')
    while True:
        print "TEST: tick"
        dev.flush()
        dev.read(1024*1024)
        time.sleep(1)


def test_devices_write():
    """
    Inf write into /dev/null device
    """
    print "TEST: devices write"
    print "TEST: wait for input"
    raw_input()

    dev = open("/dev/null", 'w')
    buf = ""
    for _ in range(1024*1024):
        buf += '\x00'
    while True:
        print "TEST: tick"
        dev.write(buf)
        dev.flush()
        time.sleep(1)


def main():
    """
    Main (infinite) loop.
    """
    if len(sys.argv) < 2:
        print "FAIL: Incorrect usage (%s)" % sys.argv
        return -1
    args = sys.argv[2:]
    if sys.argv[1] == "smoke":
        test_smoke(args)
    elif sys.argv[1] == "memfill":
        test_memfill(args)
    elif sys.argv[1] == "cpu":
        test_cpu(args)
    elif sys.argv[1] == "devices":
        test_devices(args)
    else:
        print "FAIL: No test specified (%s)" % sys.argv

if __name__ == "__main__":
    main()
