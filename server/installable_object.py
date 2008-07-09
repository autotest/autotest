from autotest_lib.server import utils


class InstallableObject(object):
    """
    This class represents a software package that can be installed on
    a Host.

    Implementation details:
    This is an abstract class, leaf subclasses must implement the methods
    listed here. You must not instantiate this class but should
    instantiate one of those leaf subclasses.
    """

    source_material= None

    def __init__(self):
        super(InstallableObject, self).__init__()


    def get(self, location):
        """
        Get the source material required to install the object.

        Through the utils.get() function, the argument passed will be
        saved in a temporary location on the LocalHost. That location
        is saved in the source_material attribute.

        Args:
                location: the path to the source material. This path
                        may be of any type that the utils.get()
                        function will accept.
        """
        self.source_material= utils.get(location)


    def install(self, host):
        pass
