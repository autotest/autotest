"""
This module defines the BaseFsdevManager Class which provides an
implementation of the 'fsdev' helper API; site specific extensions
to any of these methods should inherit this class.
"""

from autotest_lib.client.bin import utils

class BaseFsdevManager(object):

    def __init__(self):
        pass


    def include_partition(self, partname):
        # Client to fill in logic that will pick the right partitions
        return False


    def map_drive_name(self, partname):
        return partname


SiteFsdevManager = utils.import_site_class(
    __file__, "autotest_lib.client.bin.site_fsdev", "SiteFsdevManager",
    BaseFsdevManager)

# Wrap whatever SiteFsdevManager class we've found above in a class
class FsdevManager(SiteFsdevManager):
    pass
