"""
    Utility module standardized on ElementTree 2.6 to minimize dependencies
    in python 2.4 systems.
"""

try:
    import autotest.common as common
except ImportError:
    import common

from autotest.client.shared import ElementTree
