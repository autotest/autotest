from autotest.client.shared import error
from autotest.client.virt import installer
from autotest.client.virt import base_installer


def run_build(test, params, env):
    """
    Installs virtualization software using the selected installers

    @param test: test object.
    @param params: Dictionary with test parameters.
    @param env: Test environment.
    """
    srcdir = params.get("srcdir", test.srcdir)
    params["srcdir"] = srcdir

    # Flag if a installer minor failure ocurred
    minor_failure = False
    minor_failure_reasons = []

    try:
        for name in params.get("installers", "").split():
            installer_obj = installer.make_installer(name, params, test)
            installer_obj.install()
            if installer_obj.minor_failure == True:
                minor_failure = True
                reason = "%s_%s: %s" % (installer_obj.name,
                                        installer_obj.mode,
                                        installer_obj.minor_failure_reason)
                minor_failure_reasons.append(reason)
            env.register_installer(installer_obj)

    except Exception, e:
        # if the build/install fails, don't allow other tests
        # to get a installer.
        msg = "Virtualization software install failed: %s" % (e)
        env.register_installer(base_installer.FailedInstaller(msg))
        raise

    if minor_failure:
        raise error.TestWarn("Minor (worked around) failures during build "
                             "test: %s" % ", ".join(minor_failure_reasons))
