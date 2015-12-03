import logging
import os
import shutil

from autotest.client import utils
from autotest.client.shared import error, kernel_versions


def apply_overrides(orig_file, changes_file, output_file):
    override = dict()

    # First suck all the changes into a dictionary.
    input_file = file(changes_file, 'r')
    for line in input_file.readlines():
        if line.startswith('CONFIG_'):
            key = line.split('=')[0]
            override[key] = line
        elif line.startswith('# CONFIG_'):
            key = line.split(' ')[1]
            override[key] = line
    input_file.close()

    # Now go through the input file, overriding lines where need be
    input_file = file(orig_file, 'r')
    output_file = file(output_file, 'w')
    for line in input_file.readlines():
        if line.startswith('CONFIG_'):
            key = line.split('=')[0]
        elif line.startswith('# CONFIG_'):
            key = line.split(' ')[1]
        else:
            key = None
        if key and key in override:
            output_file.write(override[key])
        else:
            output_file.write(line)
    input_file.close()
    output_file.close()


def diff_configs(old, new):
    utils.system('diff -u %s %s > %s' % (old, new, new + '.diff'),
                 ignore_status=True)


def feature_enabled(feature, config):
    """
    Verify whether a given kernel option is enabled.

    :param feature: Kernel feature, such as "CONFIG_DEFAULT_UIMAGE".
    :param config: Config file path, such as /tmp/config.
    """
    return utils.grep('^%s=y' % feature, config)


def modules_needed(config):
    return (feature_enabled('CONFIG_MODULES', config) and
            utils.grep('=m', config))


def config_by_name(name, s):
    version = kernel_versions.version_choose_config(name, s[1:])
    if version:
        return s[0] + version
    return None


class kernel_config(object):

    """
    Build directory must be ready before init'ing config.

    Stages:
           1. Get original config file
           2. Apply overrides
           3. Do 'make oldconfig' to update it to current source code
                      (gets done implicitly during the process)

    You may specifiy the defconfig within the tree to build,
    or a custom config file you want, or None, to get machine's
    default config file from the repo.
    """

    def __init__(self, job, build_dir, config_dir, orig_file, overrides,
                 defconfig=False, name=None, make=None):
        self.build_dir = build_dir
        self.config_dir = config_dir
        self.orig_config = os.path.join(config_dir, 'config.orig')
        running_config = utils.running_config()
        if running_config is None:
            running_config = ''
        if running_config.endswith('.gz'):
            tmp_running_config = '/tmp/running_config'
            utils.system('cat %s | gunzip > %s' %
                         (running_config, tmp_running_config))
            running_config = tmp_running_config

        self.running_config = running_config

        # 1. Get original config file
        self.build_config = os.path.join(build_dir, '.config')
        if (orig_file == '' and not defconfig and not make):  # use user default
            s = job.config_get("kernel.default_config_set")
            defconf = None
            if s and name:
                defconf = config_by_name(name, s)
            if not defconf:
                defconf = job.config_get("kernel.default_config")
            if defconf:
                orig_file = defconf
            else:
                if self.running_config:
                    orig_file = self.running_config
        if (orig_file == '' and not make and defconfig):  # use defconfig
            make = 'defconfig'
        if (orig_file == '' and make):  # use the config command
            logging.debug("using %s to configure kernel" % make)
            os.chdir(build_dir)
            make_return = utils.system('make %s > /dev/null' % make)
            self.config_record(make)
            if make_return:
                raise error.TestError('make %s failed' % make)
        else:
            logging.debug("using %s to configure kernel", orig_file)
            utils.get_file(orig_file, self.orig_config)
            self.update_config(self.orig_config, self.orig_config + '.new')
            diff_configs(self.orig_config, self.orig_config + '.new')

        # 2. Apply overrides
        if overrides:
            logging.debug("using %s to re-configure kernel", overrides)
            self.over_config = os.path.join(config_dir, 'config.over')
            overrides_local = self.over_config + '.changes'
            utils.get_file(overrides, overrides_local)
            apply_overrides(self.build_config, overrides_local, self.over_config)
            self.update_config(self.over_config, self.over_config + '.new')
            diff_configs(self.over_config, self.over_config + '.new')
        else:
            self.over_config = self.orig_config

    def update_config(self, old_config, new_config=None):
        os.chdir(self.build_dir)
        shutil.copyfile(old_config, self.build_config)
        utils.system('yes "" | make oldconfig > /dev/null')
        if new_config is not None:
            shutil.copyfile(self.build_config, new_config)

    def config_record(self, name):
        """
        Copy the current .config file to the config.<name>[.<n>]
        """
        i = 1
        to = os.path.join(self.config_dir, 'config.%s' % name)
        while os.path.exists(to):
            i += 1
            to = os.path.join(self.config_dir, 'config.%s.%d' % (name, i))
        shutil.copyfile(os.path.join(self.build_dir, '.config'), to)
