__author__ = """Copyright Martin J. Bligh, 2006"""

import os,os.path,shutil,urllib,copy,pickle,re
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

	def __init__(self, job, top_directory, base_tree, leave = 0):
		"""Initialize the kernel build environment

		job
			which job this build is part of
		top_directory
			top of the build environment
		base_tree
			base kernel tree. Can be one of the following:
				1. A local tarball
				2. A URL to a tarball
				3. A local directory (will symlink it)
				4. A shorthand expandable (eg '2.6.11-git3')
		"""
		self.job = job
		autodir = job.autodir
		self.top_dir = top_directory
		if not self.top_dir.startswith(autodir):
			raise
		if os.path.isdir(self.top_dir) and not leave:
			system('rm -rf ' + self.top_dir)
		os.mkdir(self.top_dir)

		self.build_dir  = os.path.join(self.top_dir, 'build')
			# created by get_kernel_tree
		self.src_dir    = os.path.join(self.top_dir, 'src')
		self.patch_dir  = os.path.join(self.top_dir, 'patches')
		self.config_dir = os.path.join(self.top_dir, 'config')
		self.log_dir    = os.path.join(self.top_dir, 'log')
		os.mkdir(self.src_dir)
		os.mkdir(self.patch_dir)
		os.mkdir(self.config_dir)
		os.mkdir(self.log_dir)

 		self.target_arch = None
		self.build_target = 'bzImage'

		if leave:
			return

		if os.path.exists(base_tree):
			self.get_kernel_tree(base_tree)
		else:
 			base_components = kernelexpand(base_tree)
			print 'kernelexpand: '
			print base_components
			self.get_kernel_tree(base_components.pop(0))
			if base_components:      # apply remaining patches
				self.patch(*base_components)


	def patch(self, *patches):
		"""Apply a list of patches (in order)"""
		print 'Applying patches: ', patches
		# self.job.stdout.redirect(os.path.join(self.log_dir, 'stdout'))
		local_patches = self.get_patches(patches)
		self.apply_patches(local_patches)
		# self.job.stdout.restore()


	def config(self, config_file, config_list = None):
		self.job.stdout.redirect(os.path.join(self.log_dir, 'stdout'))
		config = kernel_config.kernel_config(self.build_dir, self.config_dir, config_file, config_list)
		self.job.stdout.restore()


	def get_patches(self, patches):
		"""fetch the patches to the local patch_dir"""
		local_patches = []
		for patch in patches:
			dest = os.path.join(self.patch_dir, basename(patch))
			get_file(patch, dest)
			local_patches.append(dest)
		return local_patches

	
	def apply_patches(self, local_patches):
		"""apply the list of patches, in order"""
		builddir = self.build_dir
		os.chdir(builddir)

		print "apply_patches: ", local_patches
		if not local_patches:
			return None
		for patch in local_patches:
			print 'Patching from', basename(patch), '...'
			cat_file_to_cmd(patch, 'patch -p1')
	
	
  	def get_kernel_tree(self, base_tree):
		"""Extract/link base_tree to self.top_dir/build"""
  
		# if base_tree is a dir, assume uncompressed kernel
		if os.path.isdir(base_tree):
			print 'Symlinking existing kernel source'
			os.symlink(base_tree,
				   os.path.join(self.top_dir, 'build'))

		# otherwise, extract tarball
		else:
			os.chdir(self.top_dir)
			tarball = os.path.join('src', basename(base_tree))
			get_file(base_tree, tarball)

			print 'Extracting kernel tarball:', tarball, '...'
			extract_tarball_to_dir(tarball, 'build')


	def extraversion(self, tag, append=1):
		os.chdir(self.build_dir)
		if append:
			p = 's/^EXTRAVERSION =\(.*\)/EXTRAVERSION = \1-%s/' % \
									tag
		else:
			p = 's/^EXTRAVERSION =\(.*\)/EXTRAVERSION = -%s/' % \
									tag
		system('sed "%s" Makefile' % p)


	def build(self, make_opts = '', logfile = '', extraversion='autotest'):
		"""build the kernel
	
		make_opts
			additional options to make, if any
		"""
		if logfile == '':
			logfile = os.path.join(self.log_dir, 'kernel_build')
		os.chdir(self.build_dir)
		if extraversion:
			self.extraversion(extraversion)
		print os.path.join(self.log_dir, 'stdout')
		self.job.stdout.redirect(logfile + '.stdout')
		self.job.stderr.redirect(logfile + '.stderr')
		self.set_cross_cc()
		# setup_config_file(config_file, config_overrides)

		# Not needed on 2.6, but hard to tell -- handle failure
		system('make dep', ignorestatus=1)
		threads = 2 * count_cpus()
		build_string = 'make -j %d %s %s' % (threads, make_opts,
					     self.build_target)
					# eg make bzImage, or make zImage
		print build_string
		system(build_string)
		if kernel_config.modules_needed('.config'):
			system('make modules')

		self.job.stdout.restore()
		self.job.stderr.restore()


	def build_timed(self, threads, timefile = '/dev/null', make_opts = ''):
		"""time the bulding of the kernel"""
		os.chdir(self.build_dir)
		print "make clean"
		system('make clean')
		build_string = "/usr/bin/time -o %s make %s -j %s vmlinux" % (timefile, make_opts, threads)
		print build_string
		system(build_string)
		if (not os.path.isfile('vmlinux')):
			raise TestError("no vmlinux found, kernel build failed")


	def clean(self):
		"""make clean in the kernel tree"""
		os.chdir(self.build_dir) 
		print "make clean"
		system('make clean')


	def mkinitrd(self, version, image, system_map, initrd):
		"""Build kernel initrd image.
		Try to use distro specific way to build initrd image.
		Parameters:
			version
				new kernel version
			image
				new kernel image file
			system_map
				System.map file
			initrd
				initrd image file to build
		"""
		vendor = get_os_vendor()
		
		if os.path.isfile(initrd):
			print "Existing %s file, will remove it." % initrd
			os.remove(initrd)
			
		if vendor in ['Red Hat', 'Fedora Core']:
			system('mkinitrd %s %s' % (initrd, version))
		elif vendor in ['SUSE']:
			system('mkinitrd -k %s -i %s -M %s' % (image, initrd, system_map))
		else:
			raise TestError('Unsupported vendor %s' % vendor)


	def install(self, tag='autotest', prefix = '/'):
		"""make install in the kernel tree"""
		os.chdir(self.build_dir)
		
		if not os.path.isdir(prefix):
			os.mkdir(prefix)
		boot_dir = os.path.join(prefix, 'boot')
		if not os.path.isdir(boot_dir):
			os.mkdir(boot_dir)

		arch = get_file_arch('vmlinux')
		image = os.path.join('arch', arch, 'boot', self.build_target)
		force_copy(image, boot_dir + '/vmlinuz-' + tag)
		force_copy('vmlinux', boot_dir + '/vmlinux-' + tag)
		force_copy('System.map', boot_dir + '/System.map-' + tag)
		force_copy('.config', boot_dir + '/config-' + tag)
	
		if not kernel_config.modules_needed('.config'):
			return

		system('make modules_install INSTALL_MOD_PATH=%s' % prefix)
		if prefix == '/':
			self.mkinitrd(self.get_kernel_build_ver(), image, \
				     'System.map', boot_dir + '/inird-' + tag)


	def get_kernel_build_ver(self):
		"""Check Makefile and .config to return kernel version"""
		version = patchlevel = sublevel = extraversion = localversion = ''

		for line in open(self.build_dir + '/Makefile', 'r').readlines():
			if line.startswith('VERSION'):
				version = line[line.index('=') + 1:].strip()
			if line.startswith('PATCHLEVEL'):
				patchlevel = line[line.index('=') + 1:].strip()
			if line.startswith('SUBLEVEL'):
				sublevel = line[line.index('=') + 1:].strip()
			if line.startswith('EXTRAVERSION'):
				extraversion = line[line.index('=') + 1:].strip()

		for line in open(self.build_dir + '/.config', 'r').readlines():
			if line.startswith('CONFIG_LOCALVERSION='):
				localversion = line.rstrip().split('"')[1]

		return "%s.%s.%s%s%s" %(version, patchlevel, sublevel, extraversion, localversion)		


	def set_cross_cc(self, target_arch=None, cross_compile=None,
			 build_target='bzImage'):
		"""Set up to cross-compile.
			This is broken. We need to work out what the default
			compile produces, and if not, THEN set the cross
			compiler.
		"""

		if self.target_arch:
			return
		
		self.build_target = build_target
		
		# If no 'target_arch' given assume native compilation
		if target_arch == None:
			target_arch = get_kernel_arch()
			if target_arch == 'ppc64':
				if self.build_target == 'bzImage':
					self.build_target = 'zImage'
			
		return                 # HACK. Crap out for now.

		# At this point I know what arch I *want* to build for
		# but have no way of working out what arch the default
		# compiler DOES build for.

		# Oh, and BTW, install_package() doesn't exist yet.
	
		if target_arch == 'ppc64':
			install_package('ppc64-cross')
			cross_compile = os.path.join(autodir, 'sources/ppc64-cross/bin')

		elif target_arch == 'x86_64':
			install_package('x86_64-cross')
			cross_compile = os.path.join(autodir, 'sources/x86_64-cross/bin')

		os.environ['ARCH'] = self.target_arch = target_arch

		self.cross_compile = cross_compile
		if self.cross_compile:
			os.environ['CROSS_COMPILE'] = self.cross_compile

	
	def pickle_dump(self, filename):
		"""dump a pickle of ourself out to the specified filename

		we can't pickle the backreference to job (it contains fd's), 
		nor would we want to
		"""
		temp = copy.copy(self)
		temp.job = None
		pickle.dump(temp, open(filename, 'w'))

