#!/usr/bin/python

__author__ = "raphtee@google.com (Travis Miller)"

import mock
import pdb

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


# say we want to test that do_stuff is doing what we think it is doing
def do_stuff(a, b, func):
	print b.method1()
	print b.method3(10)
	print func("how many")
	print a.method2(5)
	print b.method1()
	print b.method2(3)
	print b.method2("hello")


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
	m2.method2.expect_call(3).and_return(6)
	m2.method2.expect_call(mock.is_string_comparator()).and_return("foo")

	# check the recording order
	for func_call in god.recording:
		print func_call[0]

	# once we start making calls into the methods we are in
	# playback mode
	do_stuff(m1, m2, f)

	# we can now check that playback succeeded
	print god.check_playback()
	

if __name__ == "__main__":
	main()
