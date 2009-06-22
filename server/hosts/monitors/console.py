#!/usr/bin/python
#
# Script for translating console output (from STDIN) into Autotest
# warning messages.

import optparse, os, sys
import monitors_util

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


def main():
    (options, args) = parser.parse_args()
    if len(args) != 2:
        parser.print_help()
        sys.exit(1)

    logfile = open(args[0], 'a', 0)
    warnfile = os.fdopen(int(args[1]), 'w', 0)
    # For now we aggregate all the alert_hooks.
    alert_hooks = []
    for patterns_path in options.pattern_paths.split(','):
        patterns_file = open(patterns_path)
        alert_hooks.extend(
            monitors_util.build_alert_hooks(patterns_file, warnfile))

    monitors_util.process_input(
        sys.stdin, logfile, options.log_timestamp_format, alert_hooks)


if __name__ == '__main__':
    main()
