#!/usr/bin/python
import sys, os, textwrap
import common
from autotest_lib.client.common_lib import control_data

if len(sys.argv) != 2:
    print "Usage %s <control file>" % os.path.basename(sys.argv[0])
    sys.exit(1)

if not os.path.exists(sys.argv[1]):
    print "File %s does not exist" % sys.argv[1]
    sys.exit(1)

try:
    cd = control_data.parse_control(sys.argv[1], True)
except Exception, e:
    print "This control file does not adhear to the spec set forth in"
    print "http://autotest.kernel.org/wiki/ControlRequirements"
    print
    print "Specific error:"
    print '\n'.join(textwrap.wrap(str(e), initial_indent='    ',
                    subsequent_indent='    '))
    sys.exit(1)

if cd.experimental:
    print textwrap.wrap("WARNING: This file is marked experimental.  It will "
                        "not show up on the autotest frontend unless "
                        "experimental is set to False.")
    sys.exit(0)

print "Control file looks good!"
