#!/usr/bin/python
"""
Program to help setup kvm test environment

@copyright: Red Hat 2010
"""

import os, sys, logging, shutil, glob
import common
from autotest_lib.client.common_lib import logging_manager
from autotest_lib.client.bin import utils
from autotest_lib.client.virt import virt_utils


def check_iso(url, destination, hash):
    """
    Verifies if ISO that can be find on url is on destination with right hash.

    This function will verify the SHA1 hash of the ISO image. If the file
    turns out to be missing or corrupted, let the user know we can download it.

    @param url: URL where the ISO file can be found.
    @param destination: Directory in local disk where we'd like the iso to be.
    @param hash: SHA1 hash for the ISO image.
    """
    file_ok = False
    if not destination:
        os.makedirs(destination)
    iso_path = os.path.join(destination, os.path.basename(url))
    if not os.path.isfile(iso_path):
        logging.warning("File %s not found", iso_path)
        logging.warning("Expected SHA1 sum: %s", hash)
        answer = utils.ask("Would you like to download it from %s?" % url)
        if answer == 'y':
            try:
                utils.unmap_url_cache(destination, url, hash, method="sha1")
                file_ok = True
            except EnvironmentError, e:
                logging.error(e)
        else:
            logging.warning("Missing file %s", iso_path)
            logging.warning("Please download it or put an exsiting copy on the "
                            "appropriate location")
            return
    else:
        logging.info("Found %s", iso_path)
        logging.info("Expected SHA1 sum: %s", hash)
        answer = utils.ask("Would you like to check %s? It might take a while" %
                           iso_path)
        if answer == 'y':
            try:
                utils.unmap_url_cache(destination, url, hash, method="sha1")
                file_ok = True
            except EnvironmentError, e:
                logging.error(e)
        else:
            logging.info("File %s present, but chose to not verify it",
                         iso_path)
            return

    if file_ok:
        logging.info("%s present, with proper checksum", iso_path)


if __name__ == "__main__":
    logging_manager.configure_logging(virt_utils.VirtLoggingConfig(),
                                      verbose=True)
    logging.info("KVM test config helper")

    logging.info("")
    logging.info("1 - Verifying directories (check if the directory structure "
                 "expected by the default test config is there)")
    base_dir = "/tmp/kvm_autotest_root"
    sub_dir_list = ["images", "isos", "steps_data"]
    for sub_dir in sub_dir_list:
        sub_dir_path = os.path.join(base_dir, sub_dir)
        if not os.path.isdir(sub_dir_path):
            logging.debug("Creating %s", sub_dir_path)
            os.makedirs(sub_dir_path)
        else:
            logging.debug("Dir %s exists, not creating" %
                          sub_dir_path)
    logging.info("")
    logging.info("2 - Creating config files from samples (copy the default "
                 "config samples to actual config files)")
    kvm_test_dir = os.path.dirname(sys.modules[__name__].__file__)
    kvm_test_dir = os.path.abspath(kvm_test_dir)
    config_file_list = glob.glob(os.path.join(kvm_test_dir, "*.cfg.sample"))
    for config_file in config_file_list:
        src_file = config_file
        dst_file = config_file.rstrip(".sample")
        if not os.path.isfile(dst_file):
            logging.debug("Creating config file %s from sample", dst_file)
            shutil.copyfile(src_file, dst_file)
        else:
            logging.debug("Config file %s exists, not touching" % dst_file)

    logging.info("")
    logging.info("3 - Verifying iso (make sure we have the OS ISO needed for "
                 "the default test set)")

    iso_name = "Fedora-15-x86_64-DVD.iso"
    fedora_dir = "pub/fedora/linux/releases/15/Fedora/x86_64/iso"
    url = os.path.join("http://download.fedoraproject.org/", fedora_dir,
                       iso_name)
    hash = "61b3407f62bac22d3a3b2e919c7fc960116012d7"
    destination = os.path.join(base_dir, 'isos', 'linux')
    path = os.path.join(destination, iso_name)
    check_iso(url, destination, hash)

    logging.info("")
    logging.info("4 - Verifying winutils.iso (make sure we have the utility "
                 "ISO needed for Windows testing)")

    logging.info("In order to run the KVM autotests in Windows guests, we "
                 "provide you an ISO that this script can download")

    url = "http://people.redhat.com/mrodrigu/kvm/winutils.iso"
    hash = "02930224756510e383c44c49bffb760e35d6f892"
    destination = os.path.join(base_dir, 'isos', 'windows')
    path = os.path.join(destination, iso_name)
    check_iso(url, destination, hash)

    logging.info("")
    logging.info("5 - Checking if qemu is installed (certify qemu and qemu-kvm "
                 "are in the place the default config expects)")
    qemu_default_paths = ['/usr/bin/qemu-kvm', '/usr/bin/qemu-img']
    for qemu_path in qemu_default_paths:
        if not os.path.isfile(qemu_path):
            logging.warning("No %s found. You might need to install qemu-kvm.",
                            qemu_path)
        else:
            logging.debug("%s present", qemu_path)
    logging.info("If you wish to change qemu-kvm to qemu or other binary path, "
                 "you will have to modify tests.cfg")

    logging.info("")
    logging.info("6 - Checking for the KVM module (make sure kvm is loaded "
                 "to accelerate qemu-kvm)")
    if not utils.module_is_loaded("kvm"):
        logging.warning("KVM module is not loaded. You might want to load it")
    else:
        logging.debug("KVM module loaded")

    logging.info("")
    logging.info("7 - Verify needed packages to get started")
    logging.info("Please take a look at the online documentation "
                 "http://www.linux-kvm.org/page/KVM-Autotest/Client_Install "
                 "(session 'Install Prerequisite packages')")

    client_dir = os.path.abspath(os.path.join(kvm_test_dir, "..", ".."))
    autotest_bin = os.path.join(client_dir, 'bin', 'autotest')
    control_file = os.path.join(kvm_test_dir, 'control')

    logging.info("")
    logging.info("When you are done fixing eventual warnings found, "
                 "you can run the kvm test using the command line AS ROOT:")
    logging.info("%s %s", autotest_bin, control_file)
    logging.info("Autotest prints the results dir, so you can look at DEBUG "
                 "logs if something went wrong")
    logging.info("You can also edit the test config files (see output of "
                 "step 2 for a list)")
