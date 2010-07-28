"""
This is a high level partition module that executes the contents of
base_partition.py and if it exists the contents of site_partition.py.
"""

from autotest_lib.client.bin.base_partition import *
try:
    from autotest_lib.client.bin.site_partition import *
except ImportError:
    pass
