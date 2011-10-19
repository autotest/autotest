from autotest_lib.client.virt import installer
from autotest_lib.client.virt import base_installer


def run_build(test, params, env):
    """
    Installs virtualization software using the selected installers

    @param test: test object.
    @param params: Dictionary with test parameters.
    @param env: Test environment.
    """
    srcdir = params.get("srcdir", test.srcdir)
    params["srcdir"] = srcdir

    try:
        for name in params.get("installers", "").split():
            installer_obj = installer.make_installer(name, params, test)
            installer_obj.install()
            env.register_installer(installer_obj)
    except Exception, e:
        # if the build/install fails, don't allow other tests
        # to get a installer.
        msg = "Virtualization software install failed: %s" % (e)
        env.register_installer(base_installer.FailedInstaller(msg))
        raise
