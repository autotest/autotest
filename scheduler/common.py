"""\
This abortion of a file is here so we can access stuff in
client/common_lib
"""

__author__ = "raphtee@google.com (Travis Miller)"

import os, sys

dirname = os.path.dirname(sys.modules[__name__].__file__)
client_dir = os.path.abspath(os.path.join(dirname, "..", 'client'))

# insert client into top of path
sys.path.insert(0, client_dir)
import common_lib
from common_lib import *

# remove top of path
del sys.path[0]

for library in common_lib.__all__:
    sys.modules['common.%s' % library] = eval(library)

# clean up the namespace
del dirname, client_dir, library
del os, sys, common_lib
