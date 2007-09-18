__author__ = """Copyright Martin J. Bligh, 2006"""

import os,os.path,shutil,urllib,copy,pickle,re,glob,time
from autotest_utils import *
import kernel_config, test, os_dep

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
		src_dir
			<tmp_dir>/src/
		build_dir
			<tmp_dir>/linux/
		config_dir
			<results_dir>/config/
		log_dir
			<results_dir>/debug/
		results_dir
			<results_dir>/results/
	"""

	autodir = ''

	def __init__(self, job, base_tree, subdir, tmp_dir, build_dir, leave = False):
		"""Initialize the kernel build environment

		job
			which job this build is part of
		base_tree
			base kernel tree. Can be one of the following:
				1. A local tarball
				2. A URL to a tarball
				3. A local directory (will symlink it)
				4. A shorthand expandable (eg '2.6.11-git3')
		subdir
			subdir in the results directory (eg "build")
			(holds config/, debug/, results/)
		tmp_dir

		leave
			Boolean, whether to leave existing tmpdir or not
		"""
		self.job = job
		self.autodir = job.autodir

		self.src_dir    = os.path.join(tmp_dir, 'src')
		self.build_dir  = os.path.join(tmp_dir, build_dir)
			# created by get_kernel_tree
		self.config_dir = os.path.join(subdir, 'config')
		self.log_dir    = os.path.join(subdir, 'debug')
		self.results_dir = os.path.join(subdir, 'results')
		self.subdir	= os.path.basename(subdir)

		if not leave:
			if os.path.isdir(self.src_dir):
				system('rm -rf ' + self.src_dir)
			if os.path.isdir(self.build_dir):
				system('rm -rf ' + self.build_dir)

		os.mkdir(self.src_dir)
		for path in [self.config_dir, self.log_dir, self.results_dir]:
			if os.path.exists(path):
				system('rm -rf ' + path)
			os.mkdir(path)

		logpath = os.path.join(self.log_dir, 'build_log')
		self.logfile = open(logpath, 'w+')

		self.target_arch = None
		self.build_target = 'bzImage'
		self.build_image = None

		if get_current_kernel_arch() == 'ia64':
			self.build_target = 'all'
			self.build_image = 'vmlinux.gz'

		if leave:
			return

		self.logfile.write('BASE: %s\n' % base_tree)

		# Where we have direct version hint record that
		# for later configuration selection.
		shorthand = re.compile(r'^\d+\.\d+\.\d+')
		if shorthand.match(base_tree):
			self.base_tree_version = base_tree
		else:
			self.base_tree_version = None
			
		if os.path.exists(base_tree):
			self.get_kernel_tree(base_tree)
		else:
			args = self.job.config_get('mirror.ftp_kernel_org')
			if args:
				args = '-l ' + args
			base_components = kernelexpand(base_tree, args)
			print 'kernelexpand: '
			print base_components
			self.get_kernel_tree(base_components.pop(0))
			if base_components:      # apply remaining patches
				self.patch(*base_components)


	def __record(self, fn, name, *args, **dargs):
		try:
			fn(*args, **dargs)
			self.job.record('GOOD', self.subdir, name)
		except Exception, detail:
			err = detail.__str__()
			self.job.record('FAIL', self.subdir, name, err)
			raise
		

	def _patch(self, *patches):
		"""Apply a list of patches (in order)"""
		if not patches:
			return
	#	if isinstance(patches, basestring):
	#		patches = [patches]
		print 'Applying patches: ', patches
		# self.job.stdout.redirect(os.path.join(self.log_dir, 'stdout'))
		self.apply_patches(self.get_patches(patches))
		# self.job.stdout.restore()


	def patch(self, *args, **dargs):
		self.__record(self._patch, "kernel.patch", *args, **dargs)


	def _config(self, config_file = '', config_list = None,
							defconfig = False):
		self.job.stdout.redirect(os.path.join(self.log_dir, 'stdout'))
		self.set_cross_cc()
		config = kernel_config.kernel_config(self.job, self.build_dir,
			 self.config_dir, config_file, config_list,
			 defconfig, self.base_tree_version)
		self.job.stdout.restore()


	def config(self, *args, **dargs):
		self.__record(self._config, "kernel.config", *args, **dargs)


	def get_patches(self, patches):
		"""fetch the patches to the local src_dir"""
		local_patches = []
		for patch in patches:
			dest = os.path.join(self.src_dir, basename(patch))
			# FIXME: this isn't unique. Append something to it
			# like wget does if it's not there?
			print "get_file %s %s %s %s" % (patch, dest, self.src_dir, basename(patch))
			get_file(patch, dest)
			# probably safer to use the command, not python library
			md5sum = system_output('md5sum ' + dest).split()[0]
			local_patches.append((patch, dest, md5sum))
		return local_patches


	def apply_patches(self, local_patches):
		"""apply the list of patches, in order"""
		builddir = self.build_dir
		os.chdir(builddir)

		if not local_patches:
			return None
		for (spec, local, md5sum) in local_patches:
			if local.endswith('.bz2') or local.endswith('.gz'):
				ref = spec
			else:
				ref = force_copy(local, self.results_dir)
				ref = self.job.relative_path(ref)
			log = 'PATCH: %s %s %s\n' % (spec, ref, md5sum)
			print log
			cat_file_to_cmd(local, 'patch -p1 > /dev/null')
			self.logfile.write(log)


	def get_kernel_tree(self, base_tree):
		"""Extract/link base_tree to self.build_dir"""
  
		# if base_tree is a dir, assume uncompressed kernel
		if os.path.isdir(base_tree):
			print 'Symlinking existing kernel source'
			os.symlink(base_tree, self.build_dir)

		# otherwise, extract tarball
		else:
			os.chdir(os.path.dirname(self.src_dir))
			# Figure out local destination for tarball
			tarball = os.path.join(self.src_dir, os.path.basename(base_tree))
			get_file(base_tree, tarball)
			print 'Extracting kernel tarball:', tarball, '...'
			extract_tarball_to_dir(tarball, self.build_dir)


	def extraversion(self, tag, append=1):
		os.chdir(self.build_dir)
		extraversion_sub = r's/^EXTRAVERSION =\s*\(.*\)/EXTRAVERSION = '
		if append:
			p = extraversion_sub + '\\1-%s/' % tag
		else:
			p = extraversion_sub + '-%s/' % tag
		system('mv Makefile Makefile.old')
		system('sed "%s" < Makefile.old > Makefile' % p)


	def _build(self, make_opts = '', logfile = '', extraversion='autotest'):
		"""build the kernel

		make_opts
			additional options to make, if any
		"""
		os_dep.commands('gcc', 'make')
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
			system('make -j %d modules' % (threads))

		self.job.stdout.restore()
		self.job.stderr.restore()

		kernel_version = self.get_kernel_build_ver()
		kernel_version = re.sub('-autotest', '', kernel_version)
		self.logfile.write('BUILD VERSION: %s\n' % kernel_version)

		force_copy(self.build_dir+'/System.map', self.results_dir)


	def build(self, *args, **dargs):
		self.__record(self._build, "kernel.build", *args, **dargs)


	def build_timed(self, threads, timefile = '/dev/null', make_opts = ''):
		"""time the bulding of the kernel"""
		os.chdir(self.build_dir)
		self.set_cross_cc()
		print "make clean"
		system('make clean')
		build_string = "/usr/bin/time -o %s make %s -j %s vmlinux" % (timefile, make_opts, threads)
		print build_string
		system(build_string)
		if (not os.path.isfile('vmlinux')):
			raise TestError("no vmlinux found, kernel build failed")


	def _clean(self):
		"""make clean in the kernel tree"""
		os.chdir(self.build_dir) 
		print "make clean"
		system('make clean')


	def clean(self, *args, **dargs):
		self.__record(self._clean, "kernel.clean", *args, **dargs)


	def _mkinitrd(self, version, image, system_map, initrd):
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
		elif vendor in ['Debian', 'Ubuntu']:
			if os.path.isfile('/usr/sbin/mkinitrd'):
				cmd = '/usr/sbin/mkinitrd'
			elif os.path.isfile('/usr/sbin/mkinitramfs'):
				cmd = '/usr/sbin/mkinitramfs'
			else:
				raise TestError('No Debian initrd builder')
			system('%s -o %s %s' % (cmd, initrd, version))
		else:
			raise TestError('Unsupported vendor %s' % vendor)


	def mkinitrd(self, *args, **dargs):
		self.__record(self._mkinitrd, "kernel.mkinitrd", *args, **dargs)


	def set_build_image(self, image):
		self.build_image = image


	def _install(self, tag='autotest', prefix = '/'):
		"""make install in the kernel tree"""
		os.chdir(self.build_dir)

		if not os.path.isdir(prefix):
			os.mkdir(prefix)
		self.boot_dir = os.path.join(prefix, 'boot')
		if not os.path.isdir(self.boot_dir):
			os.mkdir(self.boot_dir)

		if not self.build_image:
			images = glob.glob('arch/*/boot/' + self.build_target)
			if len(images):
				self.build_image = images[0]
			else:
				self.build_image = self.build_target

		# remember installed files
		self.vmlinux = self.boot_dir + '/vmlinux-' + tag
		if (self.build_image != 'vmlinux'):
			self.image = self.boot_dir + '/vmlinuz-' + tag
		else:
			self.image = self.vmlinux
		self.system_map = self.boot_dir + '/System.map-' + tag
		self.config = self.boot_dir + '/config-' + tag
		self.initrd = ''

		# copy to boot dir
		force_copy('vmlinux', self.vmlinux)
		if (self.build_image != 'vmlinux'):
			force_copy(self.build_image, self.image)
		force_copy('System.map', self.system_map)
		force_copy('.config', self.config)

		if not kernel_config.modules_needed('.config'):
			return

		system('make modules_install INSTALL_MOD_PATH=%s' % prefix)
		if prefix == '/':
			self.initrd = self.boot_dir + '/initrd-' + tag
			self.mkinitrd(self.get_kernel_build_ver(), self.image, \
						  self.system_map, self.initrd)


	def install(self, *args, **dargs):
		self.__record(self._install, "kernel.install", *args, **dargs)


	def add_to_bootloader(self, tag='autotest', args=''):
		""" add this kernel to bootloader, taking an
		    optional parameter of space separated parameters
		    e.g.:  kernel.add_to_bootloader('mykernel', 'ro acpi=off')
		"""

		# remove existing entry if present
		self.job.bootloader.remove_kernel(tag)

		# pull the base argument set from the job config,
		baseargs = self.job.config_get('boot.default_args')
		if baseargs:
			args = baseargs + " " + args
		
		# otherwise populate from /proc/cmdline
		# if not baseargs:
		#	baseargs = open('/proc/cmdline', 'r').readline().strip()
		# NOTE: This is unnecessary, because boottool does it.

		root = None
		roots = [x for x in args.split() if x.startswith('root=')]
		if roots:
			root = re.sub('^root=', '', roots[0])
		arglist = [x for x in args.split() if not x.startswith('root=')]
		args = ' '.join(arglist)

		# add the kernel entry
		# add_kernel(image, title='autotest', initrd='')
		self.job.bootloader.add_kernel(self.image, tag, self.initrd, \
						args = args, root = root)


	def get_kernel_build_arch(self, arch=None):
		"""
		Work out the current kernel architecture (as a kernel arch)
		"""
		if not arch:
			arch = get_current_kernel_arch()
		if re.match('i.86', arch):
			return 'i386'
		elif re.match('sun4u', arch):
			return 'sparc64'
		elif re.match('arm.*', arch):
			return 'arm'
		elif re.match('sa110', arch):
			return 'arm'
		elif re.match('s390x', arch):
			return 's390'
		elif re.match('parisc64', arch):
			return 'parisc'
		elif re.match('ppc.*', arch):
			return 'powerpc'
		elif re.match('mips.*', arch):
			return 'mips'
		else:
			return arch


	def get_kernel_build_release(self):
		releasem = re.compile(r'.*UTS_RELEASE\s+"([^"]+)".*');
		versionm = re.compile(r'.*UTS_VERSION\s+"([^"]+)".*');

		release = None
		version = None

		for file in [ self.build_dir + "/include/linux/version.h",
			      self.build_dir + "/include/linux/utsrelease.h",
			      self.build_dir + "/include/linux/compile.h" ]:
			if os.path.exists(file):
				fd = open(file, 'r')
				for line in fd.readlines():
					m = releasem.match(line)
					if m:
						release = m.groups()[0]
					m = versionm.match(line)
					if m:
						version = m.groups()[0]
				fd.close()

		return (release, version)

	
	def get_kernel_build_ident(self):
		(release, version) = self.get_kernel_build_release()

		if not release or not version:
			raise JobError('kernel has no identity')

		return release + '::' + version


	def boot(self, args='', once=True, ident=1):
		""" install and boot this kernel, do not care how
		    just make it happen.
		"""

		# If we can check the kernel identity do so.
		if ident:
			when = int(time.time())
			ident = self.get_kernel_build_ident()
			args += " IDENT=%d" % (when)

			self.job.next_step_prepend([kernel_check_ident,
								when, ident])

		# Install this kernel.
		self.install()
		self.add_to_bootloader(args=args, tag='autotest')
		if once:
			self.job.bootloader.boot_once('autotest')

		# Boot it.
		self.job.reboot()


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


	def set_build_target(self, build_target):
		if build_target:
			self.build_target = build_target
			print 'BUILD TARGET: %s' % self.build_target


	def set_cross_cc(self, target_arch=None, cross_compile=None,
			 build_target='bzImage'):
		"""Set up to cross-compile.
			This is broken. We need to work out what the default
			compile produces, and if not, THEN set the cross
			compiler.
		"""

		if self.target_arch:
			return

		# if someone has set build_target, don't clobber in set_cross_cc
		# run set_build_target before calling set_cross_cc
		if not self.build_target:
			self.set_build_target(build_target)

		# If no 'target_arch' given assume native compilation
		if target_arch == None:
			target_arch = get_current_kernel_arch()
			if target_arch == 'ppc64':
				if self.build_target == 'bzImage':
					self.build_target = 'vmlinux'

		if not cross_compile:
			cross_compile = self.job.config_get('kernel.cross_cc')

		if cross_compile:
			os.environ['CROSS_COMPILE'] = cross_compile
		else:
			if os.environ.has_key('CROSS_COMPILE'):
				del os.environ['CROSS_COMPILE']
	
		return                 # HACK. Crap out for now.

		# At this point I know what arch I *want* to build for
		# but have no way of working out what arch the default
		# compiler DOES build for.

		# Oh, and BTW, install_package() doesn't exist yet.

		if target_arch == 'ppc64':
			install_package('ppc64-cross')
			cross_compile = os.path.join(self.autodir, 'sources/ppc64-cross/bin')

		elif target_arch == 'x86_64':
			install_package('x86_64-cross')
			cross_compile = os.path.join(self.autodir, 'sources/x86_64-cross/bin')

		os.environ['ARCH'] = self.target_arch = target_arch

		self.cross_compile = cross_compile
		if self.cross_compile:
			os.environ['CROSS_COMPILE'] = self.cross_compile


	def pickle_dump(self, filename):
		"""dump a pickle of ourself out to the specified filename

		we can't pickle the backreference to job (it contains fd's), 
		nor would we want to. Same for logfile (fd's).
		"""
		temp = copy.copy(self)
		temp.job = None
		temp.logfile = None
		pickle.dump(temp, open(filename, 'w'))
