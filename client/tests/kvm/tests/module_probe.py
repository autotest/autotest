import re, commands, logging, os
from autotest_lib.client.common_lib import error, utils
from autotest_lib.client.virt import kvm_installer


def run_module_probe(test, params, env):
    """
    load/unload KVM modules several times.

    The test can run in two modes:

    - based on previous 'build' test: in case KVM modules were installed by a
      'build' test, we used the modules installed by the previous test.

    - based on own params: if no previous 'build' test was run,
      we assume a pre-installed KVM module. Some parameters that
      work for the 'build' can be used, then, such as 'extra_modules'.
    """

    installer_object = env.previous_installer()
    if installer_object is None:
        installer_object = kvm_installer.PreInstalledKvm()
        installer_object.set_install_params(test, params)

    logging.debug('installer object: %r', installer_object)

    mod_str = params.get("mod_list")
    if mod_str:
        mod_list = re.split("[, ]", mod_str)
        logging.debug("mod list will be: %r", mod_list)
    else:
        mod_list = installer_object.full_module_list()
        logging.debug("mod list from installer: %r", mod_list)

    # unload the modules before starting:
    installer_object._unload_modules(mod_list)

    load_count = int(params.get("load_count", 100))
    try:
        for i in range(load_count):
            try:
                installer_object.load_modules(mod_list)
            except Exception,e:
                raise error.TestFail("Failed to load modules [%r]: %s" %
                                     (installer_object.full_module_list, e))

            # unload using rmmod directly because utils.unload_module() (used by
            # installer) does too much (runs lsmod, checks for dependencies),
            # and we want to run the loop as fast as possible.
            for mod in reversed(mod_list):
                r = utils.system("rmmod %s" % (mod), ignore_status=True)
                if r <> 0:
                    raise error.TestFail("Failed to unload module %s. "
                                         "exit status: %d" % (mod, r))
    finally:
        installer_object.load_modules()
