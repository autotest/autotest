# TODO: need a function to get the newest config file older than us from
# the repo.

from autotest_utils import *

def apply_overrides(orig_file, changes_file, output_file):
	# First suck all the changes into a dictionary.
	input = file(changes_file, 'r')
	for line in input.readlines():
		[key] = line.split('=')[0:1]
		if key.startswith('CONFIG_'):
			override[key] = line;
	input.close()

	# Now go through the input file, overriding lines where need be
	input = file(orig_file, 'r')
	ouput = file(output_file, 'w')
	for line in input.readlines():
		key = line.split('=')[0:1]
		if override[key]:
			output.write(override[key])
		else:
			output.write(line)
	input.close()
	output.close()


def diff_configs(old, new):
	system('diff -u %s %s > %s' % (old, new, new + '.diff'), ignorestatus=1)



def modules_needed(config):
	return (grep('CONFIG_MODULES=y', config) and grep('=m', config))

class kernel_config:
	# Build directory must be ready before init'ing config.
	# 
	# Stages:
	# 	1. Get original config file
	#	2. Apply overrides
	#	3. Do 'make oldconfig' to update it to current source code
	#                  (gets done implicitly during the process)
	#
	# You may specifiy the a defconfig within the tree to build,
	# or a custom config file you want, or None, to get machine's
	# default config file from the repo.

	build_dir = ''		# the directory we're building in
	config_dir = ''		# local repository for config_file data

	build_config = ''	# the config file in the build directory
	orig_config = ''	# the original config file
	over_config = ''	# config file + overrides

	def __init__(self, build_dir, config_dir, orig_file, overrides):
		self.build_dir = build_dir
		self.config_dir = config_dir

		# 	1. Get original config file
		self.build_config = build_dir + '/.config'
		self.orig_config = config_dir + '/config.orig'
		get_file(orig_file, self.orig_config)
		self.update_config(self.orig_config, self.orig_config+'.new')
		diff_configs(self.orig_config, self.orig_config+'.new')

		#	2. Apply overrides
		if overrides:
			self.over_config = config_dir + '/config.over'
			apply_overrides(self.orig_config, overrides, over_config)
			self.update_config(self.over_config, self.over_config+'.new')
			diff_configs(self.over_config, self.over_config+'.new')
		else:
			self.over_config = self.orig_config


	def update_config(self, old_config, new_config = 'None'):
		os.chdir(self.build_dir)
		shutil.copyfile(old_config, self.build_config)
		system('yes "" | make oldconfig > /dev/null')
		if new_config:
			shutil.copyfile(self.build_config, new_config)

