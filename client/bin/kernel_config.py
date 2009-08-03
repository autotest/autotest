# TODO: need a function to get the newest config file older than us from
# the repo.

import shutil, os
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error, kernel_versions

def apply_overrides(orig_file, changes_file, output_file):
    override = dict()

    # First suck all the changes into a dictionary.
    input = file(changes_file, 'r')
    for line in input.readlines():
        if line.startswith('CONFIG_'):
            key = line.split('=')[0]
            override[key] = line;
        elif line.startswith('# CONFIG_'):
            key = line.split(' ')[1]
            override[key] = line;
    input.close()

    # Now go through the input file, overriding lines where need be
    input = file(orig_file, 'r')
    output = file(output_file, 'w')
    for line in input.readlines():
        if line.startswith('CONFIG_'):
            key = line.split('=')[0]
        elif line.startswith('# CONFIG_'):
            key = line.split(' ')[1]
        else:
            key = None
        if key and key in override:
            output.write(override[key])
        else:
            output.write(line)
    input.close()
    output.close()


def diff_configs(old, new):
    utils.system('diff -u %s %s > %s' % (old, new, new + '.diff'),
                 ignore_status=True)



def modules_needed(config):
    return (utils.grep('CONFIG_MODULES=y', config) and utils.grep('=m', config))


def config_by_name(name, set):
    version = kernel_versions.version_choose_config(name, set[1:])
    if version:
        return set[0] + version
    return None


class kernel_config(object):
    # Build directory must be ready before init'ing config.
    #
    # Stages:
    #       1. Get original config file
    #       2. Apply overrides
    #       3. Do 'make oldconfig' to update it to current source code
    #                  (gets done implicitly during the process)
    #
    # You may specifiy the a defconfig within the tree to build,
    # or a custom config file you want, or None, to get machine's
    # default config file from the repo.

    build_dir = ''          # the directory we're building in
    config_dir = ''         # local repository for config_file data

    build_config = ''       # the config file in the build directory
    orig_config = ''        # the original config file
    over_config = ''        # config file + overrides


    def __init__(self, job, build_dir, config_dir, orig_file,
                            overrides, defconfig = False, name = None, make = None):
        self.build_dir = build_dir
        self.config_dir = config_dir

        #       1. Get original config file
        self.build_config = build_dir + '/.config'
        if (orig_file == '' and not defconfig and not make):    # use user default
            set = job.config_get("kernel.default_config_set")
            defconf = None
            if set and name:
                defconf = config_by_name(name, set)
            if not defconf:
                defconf = job.config_get("kernel.default_config")
            if defconf:
                orig_file = defconf
        if (orig_file == '' and not make and defconfig):        # use defconfig
            make = 'defconfig'
        if (orig_file == '' and make): # use the config command
            print "kernel_config: using " + make + " to configure kernel"
            os.chdir(build_dir)
            make_return = utils.system('make %s > /dev/null' % make)
            self.config_record(make)
            if (make_return):
                raise error.TestError('make % failed' % make)
        else:
            print "kernel_config: using " + orig_file + \
                                            " to configure kernel"
            self.orig_config = config_dir + '/config.orig'
            utils.get_file(orig_file, self.orig_config)
            self.update_config(self.orig_config, self.orig_config+'.new')
            diff_configs(self.orig_config, self.orig_config+'.new')


        #       2. Apply overrides
        if overrides:
            print "kernel_config: using " + overrides + \
                                            " to re-configure kernel"
            self.over_config = config_dir + '/config.over'
            overrides_local = self.over_config + '.changes'
            utils.get_file(overrides, overrides_local)
            apply_overrides(self.build_config, overrides_local, self.over_config)
            self.update_config(self.over_config, self.over_config+'.new')
            diff_configs(self.over_config, self.over_config+'.new')
        else:
            self.over_config = self.orig_config


    def update_config(self, old_config, new_config = 'None'):
        os.chdir(self.build_dir)
        shutil.copyfile(old_config, self.build_config)
        utils.system('yes "" | make oldconfig > /dev/null')
        if new_config:
            shutil.copyfile(self.build_config, new_config)

    def config_record(self, name):
        #Copy the current .config file to the config.<name>[.<n>]
        i = 1
        to = self.config_dir + '/config.%s' % name
        while os.path.exists(to):
            i += 1
            to = self.config_dir + '/config.%s.%d' % (name,i)
        shutil.copyfile(self.build_dir + '/.config', to)
