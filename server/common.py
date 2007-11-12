"""\
Hook into common libraries.
"""

__author__ = 'showard@google.com (Steve Howard)'

import os, sys

dirname = os.path.dirname(__file__)
top_level_dir = os.path.abspath(os.path.join(dirname, '..', 'client'))

sys.path.insert(0, top_level_dir)
from common_lib import *
del sys.path[0]
