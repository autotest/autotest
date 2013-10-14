#!/usr/bin/python
#
# Script for translating console output (from STDIN) into Autotest
# warning messages.

import gzip
import optparse
import os
import signal
import sys
import time
import common
from autotest.server.hosts.monitors import monitors_util

PATTERNS_PATH = os.path.join(os.path.dirname(__file__), 'console_patterns')

usage = 'usage: %prog [options] logfile_name warn_fd'
parser = optparse.OptionParser(usage=usage)
parser.add_option(
    '-t', '--log_timestamp_format',
    default='[%Y-%m-%d %H:%M:%S]',
    help='Timestamp format for log messages')
parser.add_option(
    '-p', '--pattern_paths',
    default=PATTERNS_PATH,
    help='Path to alert hook patterns file')


def _open_logfile(logfile_base_name):
    """Opens an output file using the given name.

    A timestamp and compression is added to the name.

    :param logfile_base_name - The log file path without a compression suffix.
    :return: An open file like object.  Its close method must be called before
            exiting or data may be lost due to internal buffering.
    """
    timestamp = int(time.time())
    while True:
        logfile_name = '%s.%d-%d.gz' % (logfile_base_name,
                                        timestamp, os.getpid())
        if not os.path.exists(logfile_name):
            break
        timestamp += 1
    logfile = gzip.GzipFile(logfile_name, 'w')
    return logfile


def _set_logfile_close_signal_handler(logfile):
    """Setup a signal handler to explicitly call logfile.close() and exit.

    Because we are writing a compressed file we need to make sure we properly
    close to flush our internal buffer on exit. logfile_monitor.py sends us
    a SIGTERM and waits 5 seconds for before sending a SIGKILL so we have
    plenty of time to do this.

    :param logfile - An open file object to be closed on SIGTERM.
    """
    def _on_signal_close_logfile_before_exit(unused_signal_no, unused_frame):
        logfile.close()
        os.exit(1)
    signal.signal(signal.SIGTERM, _on_signal_close_logfile_before_exit)


def _unset_signal_handler():
    signal.signal(signal.SIGTERM, signal.SIG_DFL)


def main():
    (options, args) = parser.parse_args()
    if len(args) != 2:
        parser.print_help()
        sys.exit(1)

    logfile = _open_logfile(args[0])
    warnfile = os.fdopen(int(args[1]), 'w', 0)
    # For now we aggregate all the alert_hooks.
    alert_hooks = []
    for patterns_path in options.pattern_paths.split(','):
        alert_hooks.extend(monitors_util.build_alert_hooks_from_path(
            patterns_path, warnfile))

    _set_logfile_close_signal_handler(logfile)
    try:
        monitors_util.process_input(
            sys.stdin, logfile, options.log_timestamp_format, alert_hooks)
    finally:
        logfile.close()
        _unset_signal_handler()


if __name__ == '__main__':
    main()
