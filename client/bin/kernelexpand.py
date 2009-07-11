#!/usr/bin/python
#
# (C) International Business Machines 2008
# Author: Andy Whitcroft
#
# Inspired by kernelexpand by:
# (C) Martin J. Bligh 2003
#
# Released under the GPL, version 2

import sys, re, os

kernel = 'http://www.kernel.org/pub/linux/kernel/'
mappings = [
        [ r'^\d+\.\d+\.\d+$', '', True, [
                kernel + 'v%(major)s/linux-%(full)s.tar.bz2'
        ]],
        [ r'^\d+\.\d+\.\d+\.\d+$', '', True, [
                kernel + 'v%(major)s/linux-%(full)s.tar.bz2'
        ]],
        [ r'-rc\d+$', '%(minor-prev)s', True, [
                kernel + 'v%(major)s/testing/v%(minor)s/linux-%(full)s.tar.bz2',
                kernel + 'v%(major)s/testing/linux-%(full)s.tar.bz2',
        ]],
        [ r'-(git|bk)\d+$', '%(base)s', False, [
                kernel + 'v%(major)s/snapshots/old/patch-%(full)s.bz2',
                kernel + 'v%(major)s/snapshots/patch-%(full)s.bz2',
        ]],
        [ r'-mm\d+$', '%(base)s', False, [
                kernel + 'people/akpm/patches/' +
                        '%(major)s/%(base)s/%(full)s/%(full)s.bz2'
        ]],
        [ r'-mjb\d+$', '%(base)s', False, [
                kernel + 'people/mbligh/%(base)s/patch-%(full)s.bz2'
        ]]
];

def decompose_kernel_once(kernel):
    ##print "S<" + kernel + ">"
    for mapping in mappings:
        (suffix, becomes, is_full, patch_templates) = mapping

        params = {}

        match = re.search(r'^(.*)' + suffix, kernel)
        if not match:
            continue

        # Generate the parameters for the patches:
        #  full         => full kernel name
        #  base         => all but the matches suffix
        #  minor        => 2.n.m
        #  major        => 2.n
        #  minor-prev   => 2.n.m-1
        params['full'] = kernel
        params['base'] = match.group(1)

        match = re.search(r'^((\d+\.\d+)\.(\d+))', kernel)
        if not match:
            raise "unable to determine major/minor version"
        params['minor'] = match.group(1)
        params['major'] = match.group(2)
        params['minor-prev'] = match.group(2) + '.%d' % (int(match.group(3)) -1)

        # Build the new kernel and patch list.
        new_kernel = becomes % params
        patch_list = []
        for template in patch_templates:
            patch_list.append(template % params)

        return (is_full, new_kernel, patch_list)

    return (True, kernel, None)


def decompose_kernel(kernel):
    kernel_patches = []

    done = False
    while not done:
        (done, kernel, patch_list) = decompose_kernel_once(kernel)
        if patch_list:
            kernel_patches.insert(0, patch_list)
    if not len(kernel_patches):
        raise NameError('kernelexpand: %s: unknown kernel' % (kernel))

    return kernel_patches


# Look for and add potential mirrors.
def mirror_kernel_components(mirrors, components):
    new_components = []
    for component in components:
        new_patches = []
        for mirror in mirrors:
            (prefix, local) = mirror
            for patch in component:
                if patch.startswith(prefix):
                    new_patch = local + patch[len(prefix):]
                    new_patches.append(new_patch)
        for patch in component:
            new_patches.append(patch)
        new_components.append(new_patches)

    return new_components


def url_accessible(url):
    status = os.system("wget --spider -q '%s'" % (url))
    #print url + ": status=%d" % (status)

    return status == 0


def select_kernel_components(components):
    new_components = []
    for component in components:
        new_patches = []
        for patch in component:
            if url_accessible(patch):
                new_patches.append(patch)
                break
        if not len(new_patches):
            new_patches.append(component[-1])
        new_components.append(new_patches)
    return new_components


def expand_classic(kernel, mirrors):
    components = decompose_kernel(kernel)
    if mirrors:
        components = mirror_kernel_components(mirrors, components)
    components = select_kernel_components(components)

    patches = []
    for component in components:
        patches.append(component[0])

    return patches


if __name__ == '__main__':
    from optparse import OptionParser

    parser = OptionParser()

    parser.add_option("-m", "--mirror", type="string", dest="mirror",
            action="append", nargs=2, help="mirror prefix")
    parser.add_option("-v", "--no-validate", dest="validate",
            action="store_false", default=True, help="prune invalid entries")

    def usage():
        parser.print_help()
        sys.exit(1)

    options, args = parser.parse_args()

    # Check for a kernel version
    if len(args) != 1:
        usage()
    kernel = args[0]

    #mirrors = [
    #       [ 'http://www.kernel.org/pub/linux/kernel/v2.4',
    #         'http://kernel.beaverton.ibm.com/mirror/v2.4' ],
    #       [ 'http://www.kernel.org/pub/linux/kernel/v2.6',
    #         'http://kernel.beaverton.ibm.com/mirror/v2.6' ],
    #       [ 'http://www.kernel.org/pub/linux/kernel/people/akpm/patches',
    #         'http://kernel.beaverton.ibm.com/mirror/akpm' ],
    #]
    mirrors = options.mirror

    try:
        components = decompose_kernel(kernel)
    except NameError, e:
        sys.stderr.write(e.args[0] + "\n")
        sys.exit(1)

    if mirrors:
        components = mirror_kernel_components(mirrors, components)

    if options.validate:
        components = select_kernel_components(components)

    # Dump them out.
    for component in components:
        print " ".join(component)
