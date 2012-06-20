"""
Wrapper module to load native or included ElementTree module.
"""

try:
    import autotest.common as common
except ImportError:
    import common

try:
    from xml.etree.ElementTree import *
except ImportError:
    from autotest_lib.client.shared.ElementTree import *
