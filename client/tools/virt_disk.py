#!/usr/bin/env python

'''
This is a tool for that makes it easy to create virtual disks, optionally
with content ready for unattended installations.

The main use case for this tool is debugging guest installations with an
disks just like they're created by the virt unattended test installation.
'''

import sys
import optparse
import common
from virttest import utils_misc, utils_disk


class OptionParser(optparse.OptionParser):

    '''
    App option parser
    '''

    def __init__(self):
        optparse.OptionParser.__init__(self,
                                       usage=('Usage: %prog [options] '
                                              '<image_file_name> '
                                              '[file 1][file 2]..[file N]'))

        media = optparse.OptionGroup(self, 'MEDIA SELECTION')
        media.set_description('Choose only one of the media formats supported')
        media.add_option('-c', '--cdrom', dest='cdrom', default=False,
                         action='store_true',
                         help=('create a basic cdrom image'))
        media.add_option('-f', '--floppy', dest='floppy', default=False,
                         action='store_true',
                         help=('create a basic floppy image'))
        self.add_option_group(media)

        path = optparse.OptionGroup(self, 'PATH SELECTION')
        path.add_option('-q', '--qemu-img', dest='qemu_img',
                        default='/usr/bin/qemu-img',
                        help=('qemu-img binary path. defaults to '
                              '"/usr/bin/qemu-img"'))
        path.add_option('-t', '--temp', dest='temp', default='/tmp',
                        help='qemu-img binary path. defaults to "/tmp"')
        self.add_option_group(path)


class App:

    '''
    KojiPkgSpec app
    '''

    def __init__(self):
        self.opt_parser = OptionParser()

    def usage(self):
        self.opt_parser.print_help()
        sys.exit(1)

    def parse_cmdline(self):
        self.options, self.args = self.opt_parser.parse_args()
        if not (self.options.cdrom or self.options.floppy):
            self.usage()
        if (self.options.cdrom and self.options.floppy):
            self.usage()

        if not len(self.args) >= 1:
            self.usage()
        else:
            self.image = self.args[0]
            self.files = self.args[1:]

    def main(self):
        self.parse_cmdline()
        if self.options.floppy:
            self.disk = utils_disk.FloppyDisk(self.image,
                                              self.options.qemu_img,
                                              self.options.temp, self.vfd_size)
        elif self.options.cdrom:
            self.disk = utils_disk.CdromDisk(self.image,
                                             self.options.temp)

        for f in self.files:
            self.disk.copy_to(f)
        self.disk.close()


if __name__ == '__main__':
    app = App()
    app.main()
