__author__ = """Copyright Martin J. Bligh, Andy Whitcroft, 2005, 2006"""

import sys, os

class fd_stack:
	"""a stack of fd redirects

	Redirects cause existing fd's to be pushed on the stack; restore()
	causes the current set of redirects to be popped, restoring the previous
	filehandle destinations.

	Note that we need to redirect both the sys.stdout type descriptor
	(which print, etc use) and the low level OS numbered descriptor
	which os.system() etc use.
	"""

	def __init__(self, fd, filehandle):
		self.fd = fd				# eg 1
		self.filehandle = filehandle		# eg sys.stdout
		self.stack = [(fd, filehandle)]


	def update_handle(self, new):
		if (self.filehandle == sys.stdout):
			sys.stdout = new
		if (self.filehandle == sys.stderr):
			sys.stderr = new
		self.filehandle = new

	def redirect(self, filename):
		"""Redirect output to the specified file

		Overwrites the previous contents, if any.	
		"""
		self.filehandle.flush()
		fdcopy = os.dup(self.fd)
		self.stack.append( (fdcopy, self.filehandle, 0) )
		# self.filehandle = file(filename, 'w')
		if (os.path.isfile(filename)):
			newfd = os.open(filename, os.O_WRONLY)
		else:
			newfd = os.open(filename, os.O_WRONLY | os.O_CREAT)
		os.dup2(newfd, self.fd)
		os.close(newfd)
		self.update_handle(os.fdopen(self.fd, 'w'))


	def tee_redirect(self, filename):
		"""Tee output to the specified file

		Overwrites the previous contents, if any.	
		"""
		self.filehandle.flush()
		#print_to_tty("tee_redirect to " + filename)
		#where_art_thy_filehandles()
		fdcopy = os.dup(self.fd)
		r, w = os.pipe()
		pid = os.fork()
		if pid:			# parent
			os.close(r)
			os.dup2(w, self.fd)
			os.close(w)
			self.stack.append( (fdcopy, self.filehandle, pid) )
			self.update_handle(os.fdopen(self.fd, 'w', 0))
			#where_art_thy_filehandles()
			#print_to_tty("done tee_redirect to " + filename)
		else:			# child
			os.close(w)
			os.dup2(r, 0)
			os.dup2(fdcopy, 1)
			os.close(r)
			os.close(fdcopy)
			os.execlp('tee', 'tee', '-a', filename)

	
	def restore(self):
		"""unredirect one level"""
		self.filehandle.flush()
		# print_to_tty("ENTERING RESTORE %d" % self.fd)
		# where_art_thy_filehandles()
		(old_fd, old_filehandle, pid) = self.stack.pop()
		# print_to_tty("old_fd %d" % old_fd)
		# print_to_tty("self.fd %d" % self.fd)
		self.filehandle.close()   # seems to close old_fd as well.
		if pid:
			os.waitpid(pid, 0)
		# where_art_thy_filehandles()
		os.dup2(old_fd, self.fd)
		# print_to_tty("CLOSING FD %d" % old_fd)
		os.close(old_fd)
		# where_art_thy_filehandles()
		self.update_handle(old_filehandle)
		# where_art_thy_filehandles()
		# print_to_tty("EXIT RESTORE %d" % self.fd)
