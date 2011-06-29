import os, shutil, logging
from autotest_lib.client.bin import utils


def check_configure_options(script_path):
    """
    Return the list of available options (flags) of a GNU autoconf like
    configure build script.

    @param script: Path to the configure script
    """
    abspath = os.path.abspath(script_path)
    help_raw = utils.system_output('%s --help' % abspath, ignore_status=True)
    help_output = help_raw.split("\n")
    option_list = []
    for line in help_output:
        cleaned_line = line.lstrip()
        if cleaned_line.startswith("--"):
            option = cleaned_line.split()[0]
            option = option.split("=")[0]
            option_list.append(option)

    return option_list


def save_build(build_dir, dest_dir):
    logging.debug('Saving the result of the build on %s', dest_dir)
    base_name = os.path.basename(build_dir)
    tarball_name = base_name + '.tar.bz2'
    os.chdir(os.path.dirname(build_dir))
    utils.system('tar -cjf %s %s' % (tarball_name, base_name))
    shutil.move(tarball_name, os.path.join(dest_dir, tarball_name))
