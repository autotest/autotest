#!/usr/bin/python
"""
Program that calculates the md5sum for the first megabyte of a file.
It's faster than calculating the md5sum for the whole ISO image.

@copyright: Red Hat 2008-2009
@author: Uri Lublin (uril@redhat.com)
"""

import os, sys
import kvm_utils


if len(sys.argv) < 2:
    print 'usage: %s <iso-filename>' % sys.argv[0]
else:
    fname = sys.argv[1]
    if not os.access(fname, os.F_OK) or not os.access(fname, os.R_OK):
        print 'bad file name or permissions'
    else:
        print kvm_utils.md5sum_file(fname, 1024*1024)
