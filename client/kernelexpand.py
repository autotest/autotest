#!/usr/bin/python
"""
Program and API used to expand kernel versions, trying to match
them with the URL of the correspondent package on kernel.org or
a mirror. Example:

$ ./kernelexpand.py 3.1
http://www.kernel.org/pub/linux/kernel/v3.x/linux-3.1.tar.bz2

:author: Andy Whitcroft (apw@shadowen.org)
:copyright: IBM 2008
:license: GPL v2
:see: Inspired by kernelexpand by Martin J. Bligh, 2003
"""
try:
    import autotest.common as common  # pylint: disable=W0611
except ImportError:
    import common  # pylint: disable=W0611

import re
import sys
import urllib2

from autotest.client.shared.settings import settings


def get_mappings_2x():
    KERNEL_BASE_URL = settings.get_value('CLIENT', 'kernel_mirror', default='')
    GITWEB_BASE_URL = settings.get_value('CLIENT', 'kernel_gitweb', default='')
    STABLE_GITWEB_BASE_URL = settings.get_value('CLIENT', 'stable_kernel_gitweb', default='')

    MAPPINGS_2X = [
        [r'^\d+\.\d+$', '', True,
         map(lambda x: x + 'v%(major)s/linux-%(full)s.tar.bz2', KERNEL_BASE_URL.split()) +
         map(lambda x: x + ';a=snapshot;h=refs/tags/v%(full)s;sf=tgz', GITWEB_BASE_URL.split())
         ],
        [r'^\d+\.\d+\.\d+$', '', True,
         map(lambda x: x + 'v%(major)s/linux-%(full)s.tar.bz2', KERNEL_BASE_URL.split()) +
         map(lambda x: x + ';a=snapshot;h=refs/tags/v%(full)s;sf=tgz', GITWEB_BASE_URL.split())
         ],
        [r'^\d+\.\d+\.\d+\.\d+$', '', True,
         map(lambda x: x + 'v%(major)s/linux-%(full)s.tar.bz2', KERNEL_BASE_URL.split()) +
         map(lambda x: x + ';a=snapshot;h=refs/tags/v%(full)s;sf=tgz', STABLE_GITWEB_BASE_URL.split())
         ],
        [r'-rc\d+$', '%(minor-prev)s', True,
         map(lambda x: x + 'v%(major)s/testing/v%(minor)s/linux-%(full)s.tar.bz2', KERNEL_BASE_URL.split()) +
         map(lambda x: x + 'v%(major)s/testing/linux-%(full)s.tar.bz2', KERNEL_BASE_URL.split()) +
         map(lambda x: x + ';a=snapshot;h=refs/tags/v%(full)s;sf=tgz', GITWEB_BASE_URL.split())
         ],
        [r'-(git|bk)\d+$', '%(base)s', False,
         map(lambda x: x + 'v%(major)s/snapshots/old/patch-%(full)s.bz2', KERNEL_BASE_URL.split()) +
         map(lambda x: x + 'v%(major)s/snapshots/patch-%(full)s.bz2', KERNEL_BASE_URL.split())
         ],
        [r'-mm\d+$', '%(base)s', False,
         map(lambda x: x + 'people/akpm/patches/' + '%(major)s/%(base)s/%(full)s/%(full)s.bz2', KERNEL_BASE_URL.split())
         ],
        [r'-mjb\d+$', '%(base)s', False,
         map(lambda x: x + 'people/mbligh/%(base)s/patch-%(full)s.bz2', KERNEL_BASE_URL.split())
         ],
        [r'[a-f0-9]{7,40}$', '', True,
         map(lambda x: x + ';a=snapshot;h=%(full)s;sf=tgz', GITWEB_BASE_URL.split()) +
         map(lambda x: x + ';a=snapshot;h=%(full)s;sf=tgz', STABLE_GITWEB_BASE_URL.split())
         ]
    ]

    return MAPPINGS_2X


def get_mappings_post_2x():
    KERNEL_BASE_URL = settings.get_value('CLIENT', 'kernel_mirror', default='')
    GITWEB_BASE_URL = settings.get_value('CLIENT', 'kernel_gitweb', default='')
    STABLE_GITWEB_BASE_URL = settings.get_value('CLIENT', 'stable_kernel_gitweb', default='')

    MAPPINGS_POST_2X = [
        [r'^\d+\.\d+$', '', True,
         map(lambda x: x + 'v%(major)s/linux-%(full)s.tar.bz2', KERNEL_BASE_URL.split()) +
         map(lambda x: x + 'v%(major)s/linux-%(full)s.tar.xz', KERNEL_BASE_URL.split()) +
         map(lambda x: x + ';a=snapshot;h=refs/tags/v%(full)s;sf=tgz', GITWEB_BASE_URL.split())
         ],
        [r'^\d+\.\d+\.\d+$', '', True,
         map(lambda x: x + 'v%(major)s/linux-%(full)s.tar.bz2', KERNEL_BASE_URL.split()) +
         map(lambda x: x + 'v%(major)s/linux-%(full)s.tar.xz', KERNEL_BASE_URL.split()) +
         map(lambda x: x + ';a=snapshot;h=refs/tags/v%(full)s;sf=tgz', STABLE_GITWEB_BASE_URL.split())
         ],
        [r'-rc\d+$', '', True,
         map(lambda x: x + 'v%(major)s/testing/linux-%(full)s.tar.bz2', KERNEL_BASE_URL.split()) +
         map(lambda x: x + 'v%(major)s/testing/linux-%(full)s.tar.xz', KERNEL_BASE_URL.split()) +
         map(lambda x: x + ';a=snapshot;h=refs/tags/v%(full)s;sf=tgz', GITWEB_BASE_URL.split())
         ],
        [r'[a-f0-9]{7,40}$', '', True,
         map(lambda x: x + ';a=snapshot;h=%(full)s;sf=tgz', GITWEB_BASE_URL.split()) +
         map(lambda x: x + ';a=snapshot;h=%(full)s;sf=tgz', STABLE_GITWEB_BASE_URL.split())
         ]
    ]

    return MAPPINGS_POST_2X


def decompose_kernel_2x_once(kernel):
    """
    Generate the parameters for the patches (2.X version):

    full         => full kernel name
    base         => all but the matches suffix
    minor        => 2.n.m
    major        => 2.n
    minor-prev   => 2.n.m-1

    :param kernel: String representing a kernel version to be expanded.
    """
    for mapping in get_mappings_2x():
        (suffix, becomes, is_full, patch_templates) = mapping

        params = {}

        match = re.search(r'^(.*)' + suffix, kernel)
        if not match:
            continue

        params['full'] = kernel
        params['base'] = match.group(1)

        match = re.search(r'^((\d+\.\d+)\.(\d+))', kernel)
        if not match:
            raise NameError("Unable to determine major/minor version for "
                            "kernel %s" % kernel)
        params['minor'] = match.group(1)
        params['major'] = match.group(2)
        params['minor-prev'] = match.group(2) + '.%d' % (int(match.group(3)) - 1)

        # Build the new kernel and patch list.
        new_kernel = becomes % params
        patch_list = []
        for template in patch_templates:
            patch_list.append(template % params)

        return (is_full, new_kernel, patch_list)

    return (True, kernel, None)


def decompose_kernel_post_2x_once(kernel):
    """
    Generate the parameters for the patches (post 2.X version):

    full         => full kernel name
    base         => all but the matches suffix
    minor        => o.n.m
    major        => o.n
    minor-prev   => o.n.m-1

    :param kernel: String representing a kernel version to be expanded.
    """
    for mapping in get_mappings_post_2x():
        (suffix, becomes, is_full, patch_templates) = mapping

        params = {}

        match = re.search(r'^(.*)' + suffix, kernel)
        if not match:
            continue

        params['full'] = kernel
        params['base'] = match.group(1)
        major = ''

        match = re.search(r'^((\d+\.\d+)\.(\d+))', kernel)
        if not match:
            match = re.search(r'^(\d+\.\d+)', kernel)
            if not match:
                match = re.search(r'^([a-f0-9]{7,40})', kernel)
                if not match:
                    raise NameError("Unable to determine major/minor version for "
                                    "kernel %s" % kernel)
            else:
                params['minor'] = 0
                major = match.group(1)
                params['minor-prev'] = match.group(1)
        else:
            params['minor'] = match.group(1)
            major = match.group(1)
            params['minor-prev'] = match.group(2) + '.%d' % (int(match.group(3)) - 1)

        # Starting with kernels 3.x, we have folders named '3.x' on kernel.org
        first_number = major.split('.')[0]
        params['major'] = '%s.x' % first_number

        # It makes no sense a 3.1.1-rc1 version, for example
        if re.search(r'-rc\d+$', params['full']) and params['minor'] != 0:
            continue

        # Build the new kernel and patch list.
        new_kernel = becomes % params
        patch_list = []
        for template in patch_templates:
            patch_list.append(template % params)

        return (is_full, new_kernel, patch_list)

    return (True, kernel, None)


def decompose_kernel(kernel):
    match = re.search(r'^(\d+\.\d+)', kernel)
    if not match:
        match = re.search(r'^([a-f0-9]{7,40})', kernel)
        if not match:
            raise NameError("Unable to determine major/minor version for "
                            "kernel %s" % kernel)
        else:
            decompose_func = decompose_kernel_post_2x_once
    else:
        if int(match.group(1).split('.')[0]) == 2:
            decompose_func = decompose_kernel_2x_once
        elif int(match.group(1).split('.')[0]) > 2:
            decompose_func = decompose_kernel_post_2x_once

    kernel_patches = []
    done = False
    while not done:
        (done, kernel, patch_list) = decompose_func(kernel)
        if patch_list:
            kernel_patches.insert(0, patch_list)
    if not len(kernel_patches):
        doc_url = 'https://github.com/autotest/autotest/wiki/KernelSpecification'
        raise NameError("Kernel '%s' not found. "
                        "Check %s for kernel spec docs." %
                        (kernel, doc_url))

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
    try:
        u = urllib2.urlopen(url)
        u.close()
        return True
    except urllib2.HTTPError:
        return False


def select_kernel_components(components):
    new_components = []
    for component in components:
        new_patches = []
        for patch in component:
            if url_accessible(patch):
                new_patches.append(patch)
                break
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

    # Dump them out
    for component in components:
        if component:
            print(" ".join(component))
