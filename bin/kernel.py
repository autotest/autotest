
__author__ = """Copyright Martin J. Bligh, 2006"""

import os,os.path,shutil,urllib,copy,pickle
from autotest_utils import *
import kernel_config
import test

class kernel:
	""" Class for compiling kernels. 

	Data for the object includes the src files
	used to create the kernel, patches applied, config (base + changes),
	the build directory itself, and logged output

	Properties:
		job
			Backpointer to the job object we're part of
		autodir
			Path to the top level autotest dir (/usr/local/autotest)
		top_dir
			Path to the top level dir of this kernel object
		src_dir
			<top_dir>/src/
		build_dir
			<top_dir>/patches/
		config_dir
			<top_dir>/config
		log_dir
			<top_dir>/log
	"""

	autodir = ''

	def __init__(self, job, top_directory, base_tree):
		"""Initialize the kernel build environment

		job
			which job this build is part of
		top_directory
			top of the build environment
		base_tree
			???
		"""
		self.job = job
		autodir = job.autodir
		self.top_dir = top_directory
		if not self.top_dir.startswith(autodir):
			raise
		if os.path.isdir(self.top_dir):
			system('rm -rf ' + self.top_dir)
		os.mkdir(self.top_dir)

		self.build_dir  = self.top_dir + '/build'
			# created by get_kernel_tree
		self.src_dir    = self.top_dir + '/src'
		self.patch_dir  = self.top_dir + '/patches'
		self.config_dir = self.top_dir + '/config'
		self.log_dir    = self.top_dir + '/log'
		os.mkdir(self.src_dir)
		os.mkdir(self.patch_dir)
		os.mkdir(self.config_dir)
		os.mkdir(self.log_dir)

		base_tree = kernelexpand(base_tree)
		self.get_kernel_tree(base_tree)


	def patch(self, *patches):
		"""Apply a list of patches (in order)"""
		self.job.stdout.redirect(self.log_dir+'/stdout')
		local_patches = self.get_patches(patches)
		self.apply_patches(local_patches)
		self.job.stdout.restore()


	def config(self, config_file, config_list = None):
		self.job.stdout.redirect(self.log_dir+'/stdout')
		config = kernel_config.kernel_config(self.build_dir, self.config_dir, config_file, config_list)
		self.job.stdout.restore()


	def get_patches(self, patches):
		"""fetch the patches to the local patch_dir"""
		local_patches = []
		for patch in patches:
			dest = self.patch_dir + basename(patch)
			get_file(patch, dest)
			local_patches.append(dest)

	
	def apply_patches(self, patches):
		"""apply the list of patches, in order"""
		builddir = self.build_dir
		os.chdir(builddir)

		if not patches:
			return None
		for patch in patches:
			local = patch_dir + basename(patch)
			get_file(patch, local)
			print 'Patching from', basename(patch), '...'
			cat_file_to_cmd(patch, 'patch -p1')
	
	
	def get_kernel_tree(self, base_tree):
		"""Extract base_tree into self.top_dir/build"""
		os.chdir(self.top_dir)
		tarball = 'src/' + basename(base_tree)
		get_file(base_tree, tarball)

		print 'Extracting kernel tarball:', tarball, '...'
		extract_tarball_to_dir(tarball, 'build')
	

	def build(self, make_opts = ''):
		"""build the kernel
	
		make_opts
			additional options to make, if any
		"""
		os.chdir(self.build_dir)
		print self.log_dir+'stdout'
		self.job.stdout.redirect(self.log_dir+'/stdout')
		self.job.stderr.redirect(self.log_dir+'/stderr')
		self.set_cross_cc()
		# setup_config_file(config_file, config_overrides)

		# Not needed on 2.6, but hard to tell -- handle failure
		try:
			system('make dep')
		except CmdError:
			pass
		threads = 2 * count_cpus()
		system('make -j %d %s %s' % (threads, make_opts, target))
			# eg make bzImage, or make zImage
		if kernel_config.modules_needed('.config'):
			system('make modules')

		self.job.stdout.restore()
		self.job.stderr.restore()


	def build_timed(self, threads, timefile = '/dev/null', make_opts = ''):
		"""time the bulding of the kernel"""
		os.chdir(self.build_dir)
		print "make clean"
		system('make clean')
		build_string = "/usr/bin/time make %s -j %s vmlinux > /dev/null 2> %s" % (make_opts, threads, timefile)
		print build_string
		system(build_string)
		if (not os.path.isfile('vmlinux')):
			raise TestError("no vmlinux found, kernel build failed")


	def clean(self):
		"""make clean in the kernel tree"""
		os.chdir(self.build_dir) 
		print "make clean"
		system('make clean')

	
	def install(self, dir):
		"""make install in the kernel tree"""
		os.chdir(self.build_dir)
		image = 'arch/' + get_target_arch() + '/boot/' + target
		force_copy(image, '/boot/vmlinuz-autotest')
		force_copy('System.map', '/boot/System.map-autotest')
		force_copy('.config', '/boot/config-autotest')
	
		if kernel_config.modules_needed('.config'):
			system('make modules_install')
	
	
	def set_cross_cc(self):
		"""Set up to cross-compile.

		Currently this can cross-compile to ppc64 and x86_64
		"""
		target_arch = get_target_arch()
		global target
		target = 'bzImage'
	
		if target_arch == 'ppc64':
			install_package('ppc64-cross')
			os.environ['CROSS_COMPILE']=autodir+'sources/ppc64-cross/bin'
			target = 'zImage'
		elif target_arch == 'x86_64':
			install_package('x86_64-cross')
			os.environ['ARCH']='x86_64'
			os.environ['CROSS_COMPILE']=autodir+'sources/x86_64-cross/bin'


	def pickle_dump(self, filename):
		"""dump a pickle of ourself out to the specified filename

		we can't pickle the backreference to job (it contains fd's), 
		nor would we want to
		"""
		temp = copy.copy(self)
		temp.job = None
		pickle.dump(temp, open(filename, 'w'))

