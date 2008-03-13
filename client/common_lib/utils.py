import os, sys, re, shutil, urlparse, urllib, pickle, random
from error import *

def write_keyval(path, dictionary):
	if os.path.isdir(path):
		path = os.path.join(path, 'keyval')
	keyval = open(path, 'a')
	try:
		for key, value in dictionary.iteritems():
			if re.search(r'\W', key):
				raise ValueError('Invalid key: %s' % key)
			keyval.write('%s=%s\n' % (key, value))
	finally:
		keyval.close()


def is_url(path):
	"""Return true if path looks like a URL"""
	# for now, just handle http and ftp
	url_parts = urlparse.urlparse(path)
	return (url_parts[0] in ('http', 'ftp'))


def get_file(src, dest, permissions=None):
	"""Get a file from src, which can be local or a remote URL"""
	if (src == dest):
		return
	if (is_url(src)):
		print 'PWD: ' + os.getcwd()
		print 'Fetching \n\t', src, '\n\t->', dest
		try:
			urllib.urlretrieve(src, dest)
		except IOError, e:
			raise AutotestError('Unable to retrieve %s (to %s)'
					    % (src, dest), e)
	else:
		shutil.copyfile(src, dest)
	if permissions:
		os.chmod(dest, permissions)
	return dest


def unmap_url(srcdir, src, destdir='.'):
	"""
	Receives either a path to a local file or a URL.
	returns either the path to the local file, or the fetched URL

	unmap_url('/usr/src', 'foo.tar', '/tmp')
				= '/usr/src/foo.tar'
	unmap_url('/usr/src', 'http://site/file', '/tmp')
				= '/tmp/file'
				(after retrieving it)
	"""
	if is_url(src):
		url_parts = urlparse.urlparse(src)
		filename = os.path.basename(url_parts[2])
		dest = os.path.join(destdir, filename)
		return get_file(src, dest)
	else:
		return os.path.join(srcdir, src)


def update_version(srcdir, preserve_srcdir, new_version, install,
		   *args, **dargs):
	"""
	Make sure srcdir is version new_version

	If not, delete it and install() the new version.

	In the preserve_srcdir case, we just check it's up to date,
	and if not, we rerun install, without removing srcdir
	"""
	versionfile = os.path.join(srcdir, '.version')
	install_needed = True

	if os.path.exists(versionfile):
		old_version = pickle.load(open(versionfile))
		if old_version == new_version:
			install_needed = False

	if install_needed:
		if not preserve_srcdir and os.path.exists(srcdir):
			shutil.rmtree(srcdir)
		install(*args, **dargs)
		if os.path.exists(srcdir):
			pickle.dump(new_version, open(versionfile, 'w'))


class run_randomly:
	def __init__(self):
		self.test_list = []


	def add(self, *args, **dargs):
		test = (args, dargs)
		self.test_list.append(test)


	def run(self, fn):
		while self.test_list:
			test_index = random.randint(0, len(self.test_list)-1)
			(args, dargs) = self.test_list.pop(test_index)
			fn(*args, **dargs)
