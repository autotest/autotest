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
