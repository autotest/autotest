"""
Convenience functions for use by tests or whomever.

NOTE: this is a mixin library that pulls in functions from several places
Note carefully what the precendece order is

There's no really good way to do this, as this isn't a class we can do
inheritance with, just a collection of static methods.
"""
import os

from autotest_lib.client.common_lib.utils import *
from autotest_lib.client.bin.base_utils import *
if os.path.exists(os.path.join(os.path.dirname(__file__), 'site_utils.py')):
    from autotest_lib.client.bin.site_utils import *
