#!/usr/bin/python

import logging
import optparse
import re
import sys


def set_value(path, section, key, value):
    '''
    Sets a value on the configuration file

    It does so by reading all lines an rewriting the one needed. This is
    far from efficient and should only be used to perform changes to a
    handful of configuration values

    :param path:
    :param section:
    :param key:
    :param value:
    '''
    section_found = False
    section_re = re.compile(r'^\[%s\]$' % section)
    key_re = re.compile(r'^%s:\s+(.*)$' % key)

    current_lines = open(path).readlines()
    output_file = open(path, 'wb')

    for line in current_lines:
        if section_re.match(line):
            section_found = True
            output_file.write('%s' % line)
            continue

        if section_found and key_re.match(line):
            newline = '%s: %s\n' % (key, value)
            output_file.write(newline)
            section_found = False
        else:
            output_file.write('%s' % line)

    output_file.close()


class OptionParser(optparse.OptionParser):

    def __init__(self):
        optparse.OptionParser.__init__(self, usage='Usage: %prog [options]')

        self.add_option('-p', '--path',
                        help=('Path to the configuration file'))

        self.add_option('-s', '--section',
                        help=('Section in the configuration file where the key is'
                              'located at'))

        self.add_option('-k', '--key',
                        help=('Key to set a value for'))

        self.add_option('-v', '--value',
                        help=('Value to set for the key at section'))


class App(object):

    def run(self):
        result = False
        self.option_parser = OptionParser()
        opts, args = self.option_parser.parse_args()

        if not (opts.path and opts.section and opts.key and opts.value):
            logging.error("Missing required options")
            sys.exit(-1)

        set_value(opts.path, opts.section, opts.key, opts.value)


if __name__ == '__main__':
    app = App()
    result = app.run()
    sys.exit(0)
