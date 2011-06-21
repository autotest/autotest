#!/usr/bin/python
"""
Program that calculates several hashes for a given CD image.

@copyright: Red Hat 2008-2009
"""

import os, sys, optparse, logging
import common
from autotest_lib.client.common_lib import logging_manager
from autotest_lib.client.bin import utils
from autotest_lib.client.virt import virt_utils


if __name__ == "__main__":
    parser = optparse.OptionParser("usage: %prog [options] [filenames]")
    options, args = parser.parse_args()

    logging_manager.configure_logging(virt_utils.VirtLoggingConfig())

    if args:
        filenames = args
    else:
        parser.print_help()
        sys.exit(1)

    for filename in filenames:
        filename = os.path.abspath(filename)

        file_exists = os.path.isfile(filename)
        can_read_file = os.access(filename, os.R_OK)
        if not file_exists:
            logging.critical("File %s does not exist!", filename)
            continue
        if not can_read_file:
            logging.critical("File %s does not have read permissions!",
                             filename)
            continue

        logging.info("Hash values for file %s", os.path.basename(filename))
        logging.info("md5    (1m): %s", utils.hash_file(filename, 1024*1024,
                                                        method="md5"))
        logging.info("sha1   (1m): %s", utils.hash_file(filename, 1024*1024,
                                                        method="sha1"))
        logging.info("md5  (full): %s", utils.hash_file(filename, method="md5"))
        logging.info("sha1 (full): %s", utils.hash_file(filename,
                                                        method="sha1"))
        logging.info("")
