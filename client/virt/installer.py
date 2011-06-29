'''
Installer classes are responsible for building and installing virtualization
specific software components. This is the main entry point for tests that
wish to install virtualization software components.

The most common use case is to simply call make_installer() inside your tests.
'''

from autotest_lib.client.common_lib import error

__all__ = ['InstallerRegistry', 'INSTALLER_REGISTRY', 'make_installer']

class InstallerRegistry(dict):
    '''
    Holds information on known installer classes

    This class is used to create a single instance, named INSTALLER_REGISTRY,
    that will hold all information on known installer types.

    For registering a new installer class, use the register() method. If the
    virt type is not set explicitly, it will be set to 'base'. Example:

    >>> INSTALLER_REGISTRY.register('yum', base_installer.YumInstaller)

    If you want to register a virt specific installer class, set the virt
    (third) param:

    >>> INSTALLER_REGISTRY.register('yum', kvm_installer.YumInstaller, 'kvm')

    For getting a installer class, use the get_installer() method. This method
    has a fallback option 'get_default_virt' that will return a generic virt
    installer if set to true.
    '''

    DEFAULT_VIRT_NAME = 'base'

    def __init__(self, **kwargs):
        dict.__init__(self, **kwargs)
        self[self.DEFAULT_VIRT_NAME] = {}


    def register(self, mode, klass, virt=None):
        '''
        Register a class as responsible for installing virt software components

        If virt is not set, it will assume a default of 'base'.
        '''
        if virt is None:
            virt = self.DEFAULT_VIRT_NAME
        elif not self.has_key(virt):
            self[virt] = {}

        self[virt][mode] = klass


    def get_installer(self, mode, virt=None, get_default_virt=False):
        '''
        Gets a installer class that should be able to install the virt software

        Always try to use classes that are specific to the virtualization
        technology that is being tested. If you have confidence that the
        installation is rather trivial and does not require custom steps, you
        may be able to get away with a base class (by setting get_default_virt
        to True).
        '''
        if virt is None:
            virt = self.DEFAULT_VIRT_NAME
        if not self.has_key(virt):
            # return a base installer so the test could and give it a try?
            if get_default_virt:
                return self[self.DEFAULT_VIRT_NAME].get(mode)
        else:
            return self[virt].get(mode)


#
# InstallerRegistry unique instance
#
INSTALLER_REGISTRY = InstallerRegistry()


def make_installer(params, test=None):
    '''
    Installer factory: returns a new installer for the chosen mode and vm type

    This is the main entry point for acquiring an installer. Tests, such as
    the build test, should use this function.

    Param priority evaluation order is 'install_mode', then 'mode'. For virt
    type, 'vm_type' is consulted.

    @param params: dictionary with parameters generated from cartersian config
    @param test: the test instance
    '''
    mode = params.get("install_mode", params.get("mode", None))
    virt = params.get("vm_type", None)
    klass = INSTALLER_REGISTRY.get_installer(mode, virt)

    if klass is None:
        raise error.TestError('Invalid or unsupported install mode: %s' % mode)
    else:
        return klass(test, params)
