#!/usr/bin/python

__author__ = "raphtee@google.com (Travis Miller)"

import mock, mock_demo_MUT

class MyError(Exception):
    pass


class A(object):
    var = 8

    def __init__(self):
        self.x = 0

    def method1(self):
        self.x += 1
        return self.x

    def method2(self, y):
        return y * self.x

class B(A):
    def method3(self, z):
        return self.x + z

    def method4(self, z, w):
        return self.x * z + w


class C(B):
    def method5(self):
        self.method1()
        t = self.method2(4)
        u = self.method3(t)
        return u


class D(C):
    def method6(self, error):
        if error:
            raise MyError("woops")
        else:
            return 10

class E(D):
    def __init__(self, val):
        self.val = val


# say we want to test that do_stuff is doing what we think it is doing
def do_stuff(a, b, func):
    print b.method1()
    print b.method3(10)
    print func("how many")
    print a.method2(5)
    print b.method1()
    print b.method4(1, 4)
    print b.method2(3)
    print b.method2("hello")


def do_more_stuff(d):
    print d.method6(False)
    try:
        d.method6(True)
    except:
        print "caught error"


def main():
    god = mock.mock_god()

    m1 = god.create_mock_class(A, "A")
    print m1.var
    m2 = god.create_mock_class(B, "B")
    f = god.create_mock_function("func")

    print dir(m1)
    print dir(m2)

    # sets up the "recording"
    m2.method1.expect_call().and_return(1)
    m2.method3.expect_call(10).and_return(10)
    f.expect_call("how many").and_return(42)
    m1.method2.expect_call(5).and_return(0)
    m2.method1.expect_call().and_return(2)
    m2.method4.expect_call(1, 4).and_return(6)
    m2.method2.expect_call(3).and_return(6)
    m2.method2.expect_call(mock.is_string_comparator()).and_return("foo")

    # check the recording order
    for func_call in god.recording:
        print func_call

    # once we start making calls into the methods we are in
    # playback mode
    do_stuff(m1, m2, f)

    # we can now check that playback succeeded
    god.check_playback()

    # now test the ability to mock out all methods of an object
    # except those under test
    c = C()
    god.mock_up(c, "c")

    # setup recording
    c.method1.expect_call()
    c.method2.expect_call(4).and_return(4)
    c.method3.expect_call(4).and_return(5)

    # perform the test
    answer = c.method5.run_original_function()

    # check playback
    print "answer = %s" % (answer)
    god.check_playback()

    # check exception returns too
    m3 = god.create_mock_class(D, "D")
    m3.method6.expect_call(False).and_return(10)
    m3.method6.expect_call(True).and_raises(MyError("woops"))

    do_more_stuff(m3)
    god.check_playback()

    # now check we can mock out a whole class (rather than just an instance)
    mockE = god.create_mock_class_obj(E, "E")
    oldE = mock_demo_MUT.E
    mock_demo_MUT.E = mockE

    m4 = mockE.expect_new(val=7)
    m4.method1.expect_call().and_return(1)

    mock_demo_MUT.do_create_stuff()
    god.check_playback()

    mock_demo_MUT.E = oldE


if __name__ == "__main__":
    main()
