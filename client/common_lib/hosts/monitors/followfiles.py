#!/usr/bin/python
#
# Script for tailing one to many logfiles and merging their output.

import optparse, os, signal, sys

import monitors_util

usage = 'usage: %prog [options] follow_path ...'
parser = optparse.OptionParser(usage=usage)
parser.add_option(
    '-l', '--lastlines_dirpath',
    help='Path to store/read last line data to/from.')


def main():
    (options, follow_paths) = parser.parse_args()
    if len(follow_paths) < 1:
        parser.print_help()
        sys.exit(1)

    monitors_util.follow_files(
        follow_paths, sys.stdout, options.lastlines_dirpath)


if __name__ == '__main__':
    main()
