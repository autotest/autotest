__author__ = """Copyright Andy Whitcroft 2006"""

import sys
import socket
import errno
from time import time, sleep

from common.error import *


class BarrierError(JobError):
	pass

class barrier:
	""" Multi-machine barrier support

	Provides multi-machine barrier mechanism.  Execution
	stopping until all members arrive at the barrier.

	When a barrier is forming the master node (first in sort
	order) in the set accepts connections from each member
	of the set.	As they arrive they indicate the barrier
	they are joining and their identifier (their hostname
	or IP address and optional tag).  They are then asked
	to wait.  When all members are present the master node
	then checks that each member is still responding via a
	ping/pong exchange.	If this is successful then everyone
	has checked in at the barrier.  We then tell everyone
	they may continue via a rlse message.

	Where the master is not the first to reach the barrier
	the client connects will fail.  Client will retry until
	they either succeed in connecting to master or the overal
	timeout is exceeded.

	As an example here is the exchange for a three node
	barrier called 'TAG'

	  MASTER                        CLIENT1         CLIENT2
	    <-------------TAG C1-------------
	    --------------wait-------------->
	                  [...]
	    <-------------TAG C2-----------------------------
	    --------------wait------------------------------>
	                  [...]
	    --------------ping-------------->
	    <-------------pong---------------
	    --------------ping------------------------------>
	    <-------------pong-------------------------------
	            ----- BARRIER conditions MET -----
	    --------------rlse-------------->
	    --------------rlse------------------------------>

	Note that once the last client has responded to pong the
	barrier is implicitly deemed satisifed, they have all
	acknowledged their presence.  If we fail to send any
	of the rlse messages the barrier is still a success,
	the failed host has effectively broken 'right at the
	beginning' of the post barrier execution window.

	For example:
	    if ME == SERVER:
	        server start

	    b = job.barrier(ME, 'server-up', 120)
	    b.rendevous(CLIENT, SERVER)

	    if ME == CLIENT:
	        client run

	    b = job.barrier(ME, 'test-complete', 3600)
	    b.rendevous(CLIENT, SERVER)

	    if ME == SERVER:
	        server stop

	Properties:
		hostid
			My hostname/IP address + optional tag
		tag
			Symbolic name of the barrier in progress
		port
			TCP port used for this barrier
		timeout
			Maximum time to wait for a the barrier to meet
		start
			Timestamp when we started waiting
		members
			All members we expect to find in the barrier
		seen
			Number of clients seen (master)
		waiting
			Clients who have checked in and are waiting (master)
	"""

	def __init__(self, hostid, tag, timeout, port=63000):
		self.hostid = hostid
		self.tag = tag
		self.port = port
		self.timeout = timeout
		self.start = time()

		self.report("tag=%s port=%d timeout=%d start=%d" \
			% (self.tag, self.port, self.timeout, self.start))

	def report(self, out):
		print "barrier:", self.hostid, out
		sys.stdout.flush()

	def update_timeout(self, timeout):
		self.timeout = (time() - self.start) + timeout

	def remaining(self):
		timeout = self.timeout - (time() - self.start)
		if (timeout <= 0):
			raise BarrierError("timeout waiting for barrier")

		self.report("remaining: %d" % (timeout))
		return timeout

	def master_welcome(self, connection):
		(client, addr) = connection
		name = None

		client.settimeout(5)
		try:
			# Get the clients name.
			intro = client.recv(1024)
			intro = intro.strip("\r\n")

			(tag, name) = intro.split(' ')

			self.report("new client tag=%s, name=%s" % (tag, name))

			# Ok, we know who is trying to attach.  Confirm that
			# they are coming to the same meeting.  Also, everyone
			# should be using a unique handle (their IP address).
			# If we see a duplicate, something _bad_ has happened
			# so drop them now.
			if self.tag != tag:
				self.report("client arriving for the " \
								"wrong barrier")
				client.settimeout(5)
				client.send("!tag")
				client.close()
				return
			elif name in self.waiting:
				self.report("duplicate client")
				client.settimeout(5)
				client.send("!dup")
				client.close()
				return
			
			# Acknowledge the client
			client.send("wait")

		except socket.timeout:
			# This is nominally an error, but as we do not know
			# who that was we cannot do anything sane other
			# than report it and let the normal timeout kill
			# us when thats appropriate.
			self.report("client handshake timeout: (%s:%d)" %\
				(addr[0], addr[1]))
			client.close()
			return

		self.report("client now waiting: %s (%s:%d)" % \
						(name, addr[0], addr[1]))

		# They seem to be valid record them.
		self.waiting[name] = connection
		self.seen += 1

	def master_release(self):
		# Check everyone is still there, that they have not
		# crashed or disconnected in the meantime.
		allpresent = 1
		for name in self.waiting:
			(client, addr) = self.waiting[name]

			self.report("checking client present: " + name)

			client.settimeout(5)
			reply = 'none'
			try:
				client.send("ping")
				reply = client.recv(1024)
			except socket.timeout:
				self.report("ping/pong timeout: " + name)
				pass

			if reply != "pong":
				allpresent = 0

		if not allpresent:
			raise BarrierError("master lost client")
			
		# If every ones checks in then commit the release.
		for name in self.waiting:
			(client, addr) = self.waiting[name]

			self.report("releasing client: " + name)

			client.settimeout(5)
			try:
				client.send("rlse")
			except socket.timeout:	
				self.report("release timeout: " + name)
				pass
	
	def master_close(self):
		# Either way, close out all the clients.  If we have
		# not released them then they know to abort.
		for name in self.waiting:
			(client, addr) = self.waiting[name]

			self.report("closing client: " + name)
	
			try:
				client.close()
			except:
				pass

		# And finally close out our server socket.
		self.server.close()

	def master(self):
		self.report("selected as master")

		self.seen = 1
		self.waiting = {}
		self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.server.setsockopt(socket.SOL_SOCKET,
							socket.SO_REUSEADDR, 1)
		self.server.bind(('', self.port))
		self.server.listen(10)

		failed = 0
		try: 
			while 1:
				try:
					# Wait for callers welcoming each.
					self.server.settimeout(self.remaining())
					connection = self.server.accept()
					self.master_welcome(connection)
				except socket.timeout:
					self.report("timeout waiting for " +
						"remaining clients")
					pass

				# Check if everyone is here.
				self.report("master seen %d of %d" % \
					(self.seen, len(self.members)))
				if self.seen == len(self.members):
					self.master_release()
					break

			self.master_close()
		except:
			self.master_close()
			raise

	def slave(self):
		# Clip out the master host in the barrier, remove any
		# trailing local identifier following a #.  This allows
		# multiple members per host which is particularly helpful
		# in testing.
		master = (self.members[0].split('#'))[0]

		self.report("selected as slave, master=" + master)

		# Connect to them.
		remote = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		while self.remaining() > 0:
			remote.settimeout(30)
			try:
				self.report("calling master")
				remote.connect((master, self.port))
				break
			except socket.timeout:
				self.report("timeout calling master, retry")
				sleep(10)
				pass
			except socket.error, err:
				(code, str) = err
				if (code != errno.ECONNREFUSED):
					raise
				sleep(10)

		remote.settimeout(self.remaining())
		remote.send(self.tag + " " + self.hostid)

		mode = "none"
		while 1:
			# All control messages are the same size to allow
			# us to split individual messages easily.
			remote.settimeout(self.remaining())
			reply = remote.recv(4)
			if not reply:
				break

			reply = reply.strip("\r\n")
			self.report("master said: " + reply)

			mode = reply
			if reply == "ping":
				# Ensure we have sufficient time for the
				# ping/pong/rlse cyle to complete normally.
				self.update_timeout(10 * len(self.members))

				self.report("pong")
				remote.settimeout(self.remaining())
				remote.send("pong")

			elif reply == "rlse":
				# Ensure we have sufficient time for the
				# ping/pong/rlse cyle to complete normally.
				self.update_timeout(10 * len(self.members))

				self.report("was released, waiting for close")

		if mode == "rlse":
			pass
		elif mode == "wait":
			raise BarrierError("master abort -- barrier timeout")
		elif mode == "ping":
			raise BarrierError("master abort -- client lost")
		elif mode == "!tag":
			raise BarrierError("master abort -- incorrect tag")
		elif mode == "!dup":
			raise BarrierError("master abort -- duplicate client")
		else:
			raise BarrierError("master handshake failure: " + mode)

	def rendevous(self, *hosts):
		self.members = list(hosts)
		self.members.sort()

		self.report("members: " + ",".join(self.members))
		
		# Figure out who is the master in this barrier.
		if self.hostid == self.members[0]:
			self.master()
		else:
			self.slave()


#
# TESTING -- direct test harness.
#
# For example, run in parallel:
#   python bin/barrier.py 1 meeting
#   python bin/barrier.py 2 meeting
#   python bin/barrier.py 3 meeting
#
if __name__ == "__main__":
	barrier = barrier('127.0.0.1#' + sys.argv[1], sys.argv[2], 60)

	try:
		all = [ '127.0.0.1#2', '127.0.0.1#1', '127.0.0.1#3' ]
		barrier.rendevous(*all)
	except BarrierError, err:
		print "barrier: 127.0.0.1#" + sys.argv[1] + \
						": barrier failed:", err
		sys.exit(1)
	else:
		print "barrier: 127.0.0.1#" + sys.argv[1] + \
					": all present and accounted for"
		sys.exit(0)
