#!/usr/bin/python

import common

import os, shutil, re, glob
from autotest_lib.client.common_lib import utils

try:
    from autotest_lib.client.bin import site_sysinfo
    local = True
except ImportError:
    local = False

# stuff to log per reboot
files = ['/proc/pci', '/proc/meminfo', '/proc/slabinfo', '/proc/version',
        '/proc/cpuinfo', '/proc/cmdline', '/proc/modules']
# commands = ['lshw']        # this causes problems triggering CDROM drives
commands = ['uname -a', 'lspci -vvn', 'gcc --version', 'ld --version',
            'mount', 'hostname']
path = ['/usr/bin', '/bin']


def run_command(command, output):
    parts = command.split(None, 1)
    cmd = parts[0]
    if len(parts) > 1:
        args = parts[1]
    else:
        args = ''
    for dir in path:
        pathname = dir + '/' + cmd
        if not os.path.exists(pathname):
            continue
        tmp_cmd = "%s %s > %s 2> /dev/null" % (pathname, args, output)
        utils.system(tmp_cmd)


def reboot_count():
    if not glob.glob('*'):
        return -1          # No reboots, initial data not logged
    else:
        return len(glob.glob('reboot*'))


def boot_subdir(reboot_count):
    """subdir of job sysinfo"""
    if reboot_count == 0:
        return '.'
    else:
        return 'reboot%d' % reboot_count


def log_per_reboot_data(sysinfo_dir):
    """we log this data when the job starts, and again after any reboot"""
    pwd = os.getcwd()
    try:
        os.chdir(sysinfo_dir)
        subdir = boot_subdir(reboot_count() + 1)
        if not os.path.exists(subdir):
            os.mkdir(subdir)
        os.chdir(os.path.join(sysinfo_dir, subdir))
        _log_per_reboot_data()
    finally:
        os.chdir(pwd)


def _log_per_reboot_data():
    """system info to log before each step of the job"""
    for command in commands:
        run_command(command, re.sub(r'\s', '_', command))

    for file in files:
        if (os.path.exists(file)):
            shutil.copyfile(file, os.path.basename(file))

    utils.system('dmesg -c > dmesg', ignore_status=True)
    utils.system('df -mP > df', ignore_status=True)
    if local:
        site_sysinfo.log_per_reboot_data()


def log_after_each_test(test_sysinfo_dir, job_sysinfo_dir):
    """log things that change after each test (called from test.py)"""
    pwd = os.getcwd()
    try:
        os.chdir(job_sysinfo_dir)
        reboot_subdir = boot_subdir(reboot_count())
        reboot_dir = os.path.join(job_sysinfo_dir, reboot_subdir)
        assert os.path.exists(reboot_dir)

        os.makedirs(test_sysinfo_dir)
        os.chdir(test_sysinfo_dir)
        utils.system('ln -s %s reboot_current' % reboot_dir)

        utils.system('dmesg -c > dmesg', ignore_status=True)
        utils.system('df -mP > df', ignore_status=True)
        if local:
            site_sysinfo.log_after_each_test()
    finally:
        os.chdir(pwd)


def log_test_keyvals(test, test_sysinfo_dir):
    """
    Extract some useful data from the sysinfo and write it out into
    the test keyval.
    """
    keyval = {}

    # grab a bunch of single line files and turn them into keyvals
    files_to_log = ["cmdline", "uname_-a"]
    keyval_fields = ["cmdline", "uname"]
    for filename, field in zip(files_to_log, keyval_fields):
        path = os.path.join(test_sysinfo_dir, "reboot_current", filename)
        if os.path.exists(path):
            keyval["sysinfo-%s" % field] = utils.read_one_line(path)

    # grab the total memory
    path = os.path.join(test_sysinfo_dir, "reboot_current", "meminfo")
    if os.path.exists(path):
        mem_data = open(path).read()
        match = re.search(r"^MemTotal:\s+(\d+) kB$", mem_data, re.MULTILINE)
        if match:
            keyval["sysinfo-memtotal-in-kb"] = match.group(1)

    # write out the data to the test keyval file
    test.write_test_keyval(keyval)

    # call the site-specific version of this function
    if local:
        site_sysinfo.log_test_keyvals(test, test_sysinfo_dir)


if __name__ == '__main__':
    log_per_reboot_data()
