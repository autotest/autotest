import os,os.path,shutil,urllib
from autotest_utils import *
import kernel_config
import test

class kernel:
	autodir = ''

	def __init__(self, job, top_directory, base_tree):
		self.job = job
		autodir = job.autodir
		self.top_dir = top_directory
		if not self.top_dir.startswith(autodir):
			raise
		if os.path.isdir(self.top_dir):
			system('rm -rf ' + self.top_dir)
		os.mkdir(self.top_dir)

		self.src_dir    = self.top_dir + '/src'
		self.build_dir  = self.top_dir + '/build'
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
		self.job.stdout.redirect(self.log_dir+'/stdout')
		local_patches = self.get_patches(patches)
		self.apply_patches(local_patches)
		self.job.stdout.restore()


	def config(self, config_file, config_list = None):
		self.job.stdout.redirect(self.log_dir+'/stdout')
		config = kernel_config.kernel_config(self.build_dir, self.config_dir, config_file, config_list)
		self.job.stdout.restore()


	def get_patches(self, patches):
		local_patches = []
		for patch in patches:
			dest = self.patch_dir + basename(patch)
			get_file(patch, dest)
			local_patches.append(dest)

	
	def apply_patches(self, patches):
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
	# Extract base_tree into self.top_dir/build
		os.chdir(self.top_dir)
		tarball = 'src/' + basename(base_tree)
		get_file(base_tree, tarball)

		print 'Extracting kernel tarball:', tarball, '...'
		extract_tarball_to_dir(tarball, 'build')
	

	def build(self, make_opts = ''):
		# build the kernel
		os.chdir(self.build_dir)
		print self.log_dir+'stdout'
		self.job.stdout.redirect(self.log_dir+'/stdout')
		self.job.stderr.redirect(self.log_dir+'/stderr')
		self.set_cross_compiler()
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
		build_string = "/usr/bin/time make %s -j %s vmlinux > /dev/null 2> %s" % (make_opts, threads, timefile)
		print build_string
		system(build_string)
		if (not os.path.isfile('vmlinux')):
			raise TestError("no vmlinux found, kernel build failed")
		print "make clean"
		system('make clean')

	
	def install(self, dir):
		# install the kernel
		os.chdir(self.build_dir)
		image = 'arch/' + get_target_arch() + '/boot/' + target
		force_copy(image, '/boot/vmlinuz-autotest')
		force_copy('System.map', '/boot/System.map-autotest')
		force_copy('.config', '/boot/config-autotest')
	
		if kernel_config.modules_needed('.config'):
			system('make modules_install')
	
	
	def set_cross_compiler(self):
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

