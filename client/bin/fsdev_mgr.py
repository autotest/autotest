#!/usr/bin/python

"""
This module defines the BaseFsdevManager Class which provides an
implementation of the 'fsdev' helper API; site specific extensions
to any of these methods should inherit this class.
"""

class BaseFsdevManager(object):

    def __init__(self):
        pass


    def include_partition(self, partname):
        # Client to fill in logic that will pick the right partitions
        return False


    def map_drive_name(self, partname):
        return partname


# site_fsdev.py may be non-existent or empty - make sure that an appropriate
# SiteFsdevManager class is created irregardless
try:
    from site_fsdev import SiteFsdevManager
except ImportError:
    # No SiteFsdevManager class defined - supply an empty one, then
    class SiteFsdevManager(BaseFsdevManager):
        pass

# Wrap whatever SiteFsdevManager class we've found above in a class
class FsdevManager(SiteFsdevManager):
    def __init__(self):
        SiteFsdevManager.__init__(self)

