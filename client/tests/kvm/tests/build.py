from autotest_lib.client.virt import kvm_installer


def run_build(test, params, env):
    """
    Installs KVM using the selected install mode. Most install methods will
    take kvm source code, build it and install it to a given location.

    @param test: kvm test object.
    @param params: Dictionary with test parameters.
    @param env: Test environment.
    """
    srcdir = params.get("srcdir", test.srcdir)
    params["srcdir"] = srcdir

    try:
        installer_object = kvm_installer.make_installer(params)
        installer_object.set_install_params(test, params)
        installer_object.install()
        env.register_installer(installer_object)
    except Exception, e:
        # if the build/install fails, don't allow other tests
        # to get a installer.
        msg = "KVM install failed: %s" % (e)
        env.register_installer(kvm_installer.FailedInstaller(msg))
        raise
