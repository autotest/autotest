#!/usr/bin/python
"""
Program that calculates several hashes for a given CD image.

@copyright: Red Hat 2008-2009
"""

import os, sys, optparse, logging
import common, kvm_utils
from autotest_lib.client.common_lib import logging_config, logging_manager


class KvmLoggingConfig(logging_config.LoggingConfig):
    def configure_logging(self, results_dir=None, verbose=False):
        super(KvmLoggingConfig, self).configure_logging(use_console=True,
                                                        verbose=verbose)

if __name__ == "__main__":
    parser = optparse.OptionParser()
    parser.add_option('-i', '--iso', type="string", dest="filename",
                      action='store',
                      help='path to a ISO file whose hash string will be '
                           'evaluated.')

    options, args = parser.parse_args()
    filename = options.filename

    logging_manager.configure_logging(KvmLoggingConfig())

    if not filename:
        parser.print_help()
        sys.exit(1)

    filename = os.path.abspath(filename)

    file_exists = os.path.isfile(filename)
    can_read_file = os.access(filename, os.R_OK)
    if not file_exists:
        logging.critical("File %s does not exist. Aborting...", filename)
        sys.exit(1)
    if not can_read_file:
        logging.critical("File %s does not have read permissions. "
                         "Aborting...", filename)
        sys.exit(1)

    logging.info("Hash values for file %s", os.path.basename(filename))
    logging.info("md5    (1m): %s", kvm_utils.hash_file(filename, 1024*1024,
                                                        method="md5"))
    logging.info("sha1   (1m): %s", kvm_utils.hash_file(filename, 1024*1024,
                                                        method="sha1"))
    logging.info("md5  (full): %s", kvm_utils.hash_file(filename,
                                                        method="md5"))
    logging.info("sha1 (full): %s", kvm_utils.hash_file(filename,
                                                        method="sha1"))
