"""
This module defines the BaseFsdevManager Class which provides an
implementation of the 'fsdev' helper API; site specific extensions
to any of these methods should inherit this class.
"""

from autotest.client import utils


class BaseFsdevManager(object):

    def __init__(self):
        pass

    def include_partition(self, part_name):
        # Client to fill in logic that will pick the right partitions
        return False

    def map_drive_name(self, part_name):
        return part_name

    def check_mount_point(self, part_name, mount_point):
        """
        :param part_name: A partition name such as 'sda3' or similar.
        :param mount_point: A mount point such as '/usr/local' or an empty
                string if no mount point is known.

        :return: The expected mount point for part_name or a false value
                (None or '') if the client should not mount this partition.
        """
        return mount_point

    def use_partition(self, part_name):
        """
        :param part_name: A partition name such as 'sda3' or similar.

        :return: bool, should we use this partition for testing?
        """
        return True


SiteFsdevManager = utils.import_site_class(
    __file__, "autotest.client.site_fsdev", "SiteFsdevManager",
    BaseFsdevManager)

# Wrap whatever SiteFsdevManager class we've found above in a class


class FsdevManager(SiteFsdevManager):
    pass
