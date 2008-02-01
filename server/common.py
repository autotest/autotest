"""\
Hook into common libraries.
"""

__author__ = 'showard@google.com (Steve Howard)'

import os, sys

dirname = os.path.dirname(sys.modules[__name__].__file__)
top_level_dir = os.path.abspath(os.path.join(dirname, '..', 'client'))

sys.path.insert(0, top_level_dir)
import common_lib
from common_lib import *
del sys.path[0]

for library in common_lib.__all__:
        sys.modules['common.%s' % library] = eval(library)

# clean up the namespace
del dirname, top_level_dir, library
del os, sys, common_lib
