'''
Installer classes are responsible for building and installing virtualization
specific software components. This is the main entry point for tests that
wish to install virtualization software components.

The most common use case is to simply call make_installer() inside your tests.
'''

from autotest_lib.client.common_lib import error
from autotest_lib.client.virt import base_installer

__all__ = ['InstallerRegistry', 'INSTALLER_REGISTRY', 'make_installer',
           'run_installers']

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


    def get_modes(self, virt=None):
        '''
        Returns a list of all registered installer modes
        '''
        if virt is None:
            virt = self.DEFAULT_VIRT_NAME

        if not self.has_key(virt):
            return []

        return self[virt].keys()


#
# InstallerRegistry unique instance
#
INSTALLER_REGISTRY = InstallerRegistry()


#
# Register base installers
#
INSTALLER_REGISTRY.register('yum',
                            base_installer.YumInstaller)
INSTALLER_REGISTRY.register('koji',
                            base_installer.KojiInstaller)
INSTALLER_REGISTRY.register('git_repo',
                            base_installer.GitRepoInstaller)
INSTALLER_REGISTRY.register('local_src',
                            base_installer.LocalSourceDirInstaller)
INSTALLER_REGISTRY.register('local_tar',
                            base_installer.LocalSourceTarInstaller)
INSTALLER_REGISTRY.register('remote_tar',
                            base_installer.RemoteSourceTarInstaller)


def installer_name_split(fullname, virt=None):
    '''
    Split a full installer name into mode and short name

    Examples:
       git_repo_foo -> (git_repo, foo)
       local_src_foo -> (local_src, foo)
    '''
    for mode in INSTALLER_REGISTRY.get_modes(virt):
        if fullname.startswith('%s_' % mode):
            null, _name = fullname.split(mode)
            name = _name[1:]
            return (mode, name)

    return (None, None)


def make_installer(fullname, params, test=None):
    '''
    Installer factory: returns a new installer for the chosen mode and vm type

    This is the main entry point for acquiring an installer. Tests, such as
    the build test, should use this function.

    Param priority evaluation order is 'install_mode', then 'mode'. For virt
    type, 'vm_type' is consulted.

    @param fullname: the full name of instance, eg: git_repo_foo
    @param params: dictionary with parameters generated from cartersian config
    @param test: the test instance
    '''
    virt = params.get("vm_type", None)

    mode, name = installer_name_split(fullname, virt)
    if mode is None or name is None:

        error_msg = ('Invalid installer mode or name for "%s". Probably an '
                     'installer has not been registered' % fullname)
        if virt is not None:
            error_msg += ' specifically for virt type "%s"' % virt

        raise error.TestError(error_msg)

    klass = INSTALLER_REGISTRY.get_installer(mode, virt)
    if klass is None:
        raise error.TestError('Installer mode %s is not registered' % mode)
    else:
        return klass(mode, name, test, params)


def run_installers(params, test=None):
    '''
    Runs the installation routines for all installers, one at a time

    This is usually the main entry point for tests
    '''
    for name in params.get("installers", "").split():
        installer = make_installer(name, params, test)
        installer.install()
