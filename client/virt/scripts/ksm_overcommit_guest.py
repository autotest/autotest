#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Auxiliary script used to allocate memory on guests.

@copyright: 2008-2009 Red Hat Inc.
@author: Jiri Zupka (jzupka@redhat.com)
"""


import os, array, sys, random, copy, tempfile, datetime, math

PAGE_SIZE = 4096 # machine page size

TMPFS_OVERHEAD = 0.0022 # overhead on 1MB of write data


class MemFill(object):
    """
    Fills guest memory according to certain patterns.
    """
    def __init__(self, mem, static_value, random_key):
        """
        Constructor of MemFill class.

        @param mem: Amount of test memory in MB.
        @param random_key: Seed of random series used for fill up memory.
        @param static_value: Value used to fill all memory.
        """
        if (static_value < 0 or static_value > 255):
            print ("FAIL: Initialization static value"
                   "can be only in range (0..255)")
            return

        self.tmpdp = tempfile.mkdtemp()
        ret_code = os.system("mount -o size=%dM tmpfs %s -t tmpfs" %
                             ((mem+math.ceil(mem*TMPFS_OVERHEAD)),
                             self.tmpdp))
        if ret_code != 0:
            if os.getuid() != 0:
                print ("FAIL: Unable to mount tmpfs "
                       "(likely cause: you are not root)")
            else:
                print "FAIL: Unable to mount tmpfs"
        else:
            self.f = tempfile.TemporaryFile(prefix='mem', dir=self.tmpdp)
            self.allocate_by = 'L'
            self.npages = ((mem * 1024 * 1024) / PAGE_SIZE)
            self.random_key = random_key
            self.static_value = static_value
            print "PASS: Initialization"


    def __del__(self):
        if os.path.ismount(self.tmpdp):
            self.f.close()
            os.system("umount %s" % (self.tmpdp))


    def compare_page(self, original, inmem):
        """
        Compare pages of memory and print the differences found.

        @param original: Data that was expected to be in memory.
        @param inmem: Data in memory.
        """
        for ip in range(PAGE_SIZE / original.itemsize):
            if (not original[ip] == inmem[ip]): # find which item is wrong
                originalp = array.array("B")
                inmemp = array.array("B")
                originalp.fromstring(original[ip:ip+1].tostring())
                inmemp.fromstring(inmem[ip:ip+1].tostring())
                for ib in range(len(originalp)): # find wrong byte in item
                    if not (originalp[ib] == inmemp[ib]):
                        position = (self.f.tell() - PAGE_SIZE + ip *
                                    original.itemsize + ib)
                        print ("Mem error on position %d wanted 0x%Lx and is "
                               "0x%Lx" % (position, originalp[ib], inmemp[ib]))


    def value_page(self, value):
        """
        Create page filled by value.

        @param value: String we want to fill the page with.
        @return: return array of bytes size PAGE_SIZE.
        """
        a = array.array("B")
        for i in range((PAGE_SIZE / a.itemsize)):
            try:
                a.append(value)
            except:
                print "FAIL: Value can be only in range (0..255)"
        return a


    def random_page(self, seed):
        """
        Create page filled by static random series.

        @param seed: Seed of random series.
        @return: Static random array series.
        """
        random.seed(seed)
        a = array.array(self.allocate_by)
        for i in range(PAGE_SIZE / a.itemsize):
            a.append(random.randrange(0, sys.maxint))
        return a


    def value_fill(self, value=None):
        """
        Fill memory page by page, with value generated with value_page.

        @param value: Parameter to be passed to value_page. None to just use
                what's on the attribute static_value.
        """
        self.f.seek(0)
        if value is None:
            value = self.static_value
        page = self.value_page(value)
        for pages in range(self.npages):
            page.tofile(self.f)
        print "PASS: Mem value fill"


    def value_check(self, value=None):
        """
        Check memory to see if data is correct.

        @param value: Parameter to be passed to value_page. None to just use
                what's on the attribute static_value.
        @return: if data in memory is correct return PASS
                else print some wrong data and return FAIL
        """
        self.f.seek(0)
        e = 2
        failure = False
        if value is None:
            value = self.static_value
        page = self.value_page(value)
        for pages in range(self.npages):
            pf = array.array("B")
            pf.fromfile(self.f, PAGE_SIZE / pf.itemsize)
            if not (page == pf):
                failure = True
                self.compare_page(page, pf)
                e = e - 1
                if e == 0:
                    break
        if failure:
            print "FAIL: value verification"
        else:
            print "PASS: value verification"


    def static_random_fill(self, n_bytes_on_end=PAGE_SIZE):
        """
        Fill memory by page with static random series with added special value
        on random place in pages.

        @param n_bytes_on_end: how many bytes on the end of page can be changed.
        @return: PASS.
        """
        self.f.seek(0)
        page = self.random_page(self.random_key)
        random.seed(self.random_key)
        p = copy.copy(page)

        t_start = datetime.datetime.now()
        for pages in range(self.npages):
            rand = random.randint(((PAGE_SIZE / page.itemsize) - 1) -
                                  (n_bytes_on_end / page.itemsize),
                                  (PAGE_SIZE/page.itemsize) - 1)
            p[rand] = pages
            p.tofile(self.f)
            p[rand] = page[rand]

        t_end = datetime.datetime.now()
        delta = t_end - t_start
        milisec = delta.microseconds / 1e3 + delta.seconds * 1e3
        print "PASS: filling duration = %Ld ms" % milisec


    def static_random_verify(self, n_bytes_on_end=PAGE_SIZE):
        """
        Check memory to see if it contains correct contents.

        @return: if data in memory is correct return PASS
                else print some wrong data and return FAIL.
        """
        self.f.seek(0)
        e = 2
        page = self.random_page(self.random_key)
        random.seed(self.random_key)
        p = copy.copy(page)
        failure = False
        for pages in range(self.npages):
            rand = random.randint(((PAGE_SIZE/page.itemsize) - 1) -
                                  (n_bytes_on_end/page.itemsize),
                                  (PAGE_SIZE/page.itemsize) - 1)
            p[rand] = pages
            pf = array.array(self.allocate_by)
            pf.fromfile(self.f, PAGE_SIZE / pf.itemsize)
            if not (p == pf):
                failure = True
                self.compare_page(p, pf)
                e = e - 1
                if e == 0:
                    break
            p[rand] = page[rand]
        if failure:
            print "FAIL: Random series verification"
        else:
            print "PASS: Random series verification"


def die():
    """
    Quit allocator.
    """
    exit(0)


def main():
    """
    Main (infinite) loop of allocator.
    """
    print "PASS: Start"
    end = False
    while not end:
        str = raw_input()
        exec str


if __name__ == "__main__":
    main()
