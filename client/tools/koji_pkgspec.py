#!/usr/bin/env python

'''
This is a tool for that makes it easy to understand what a given KojiPkgSpec
syntax will expand to.

The main use case is making sure the packages specified in a KojiInstaller
will match the packages you intended to install.
'''

import sys, optparse
import common
from autotest.client.shared import cartesian_config
from autotest.client.virt import virt_utils


class OptionParser(optparse.OptionParser):
    '''
    KojiPkgSpec App option parser
    '''
    def __init__(self):
        optparse.OptionParser.__init__(self,
                                       usage=('Usage: %prog [options] '
                                              '[koji-pkg-spec]'))

        general = optparse.OptionGroup(self, 'GENERAL OPTIONS')
        general.add_option('-a', '--arch', dest='arch', default='x86_64',
                           help=('architecture of packages to list, together '
                                 'with "noarch". defaults to "x86_64"'))
        general.add_option('-t', '--tag', dest='tag', help='default koji tag')
        self.add_option_group(general)

        cartesian_config = optparse.OptionGroup(self, 'CARTESIAN CONFIG')
        cartesian_config.add_option('-c', '--config', dest='config',
                                    help=('use a cartesian configuration file '
                                          'for fetching package values'))

        self.add_option_group(cartesian_config)


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

        # Check for a control file if not in prebuild mode.
        if (len(self.args) < 1) and not self.options.config:
            print "Missing Package Specification!"
            self.usage()


    def get_koji_qemu_kvm_tag_pkgs(self, config_file):
        tag = None
        pkgs = None
        parser = cartesian_config.Parser(config_file)
        for d in parser.get_dicts():
            if tag is not None and pkgs is not None:
                break

            if d.has_key('koji_qemu_kvm_tag'):
                if tag is None:
                    tag = d.get('koji_qemu_kvm_tag')
            if d.has_key('koji_qemu_kvm_pkgs'):
                if pkgs is None:
                    pkgs = d.get('koji_qemu_kvm_pkgs')
        return (tag, pkgs)


    def check_koji_pkg_spec(self, koji_pkg_spec):
        if not koji_pkg_spec.is_valid():
            print 'ERROR:', koji_pkg_spec.describe_invalid()
            sys.exit(-1)


    def print_koji_pkg_spec_info(self, koji_pkg_spec):
        info = self.koji_client.get_pkg_info(koji_pkg_spec)
        if not info:
            print 'ERROR: could not find info about "%s"' % koji_pkg_spec.to_text()
            return

        name = info.get('name', 'unknown')
        pkgs = self.koji_client.get_pkg_rpm_file_names(koji_pkg_spec,
                                                       arch=self.options.arch)
        print 'Package name: %s' % name
        print 'Package files:'
        for p in pkgs:
            print '\t* %s' % p
        print


    def main(self):
        self.parse_cmdline()
        self.koji_client = virt_utils.KojiClient()
        pkgs = []

        if self.options.tag:
            virt_utils.set_default_koji_tag(self.options.tag)

        if self.options.config:
            tag, pkgs = self.get_koji_qemu_kvm_tag_pkgs(self.options.config)
            if tag is not None:
                virt_utils.set_default_koji_tag(tag)
            if pkgs is not None:
                pkgs = pkgs.split()
        else:
            pkgs = self.args

        if pkgs:
            for p in pkgs:
                koji_pkg_spec = virt_utils.KojiPkgSpec(p)
                self.check_koji_pkg_spec(koji_pkg_spec)
                self.print_koji_pkg_spec_info(koji_pkg_spec)


if __name__ == '__main__':
    app = App()
    app.main()
