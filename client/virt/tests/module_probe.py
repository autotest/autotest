import logging
from autotest.client.shared import error, utils
from autotest.client.virt import base_installer


def run_module_probe(test, params, env):
    """
    load/unload kernel modules several times.

    The test can run in two modes:

    - based on previous 'build' test: in case kernel modules were installed by a
      'build' test, we used the modules installed by the previous test.

    - based on own params: if no previous 'build' test was run,
      we assume pre-installed kernel modules.
    """
    installer_object = env.previous_installer()
    if installer_object is None:
        installer_object = base_installer.NoopInstaller('noop',
                                                        'module_probe',
                                                        test, params)
    logging.debug('installer object: %r', installer_object)

    # unload the modules before starting:
    installer_object.unload_modules()

    load_count = int(params.get("load_count", 100))
    try:
        for i in range(load_count):
            try:
                installer_object.load_modules()
            except Exception,e:
                raise error.TestFail("Failed to load modules [%r]: %s" %
                                     (installer_object.module_list, e))

            # unload using rmmod directly because utils.unload_module() (used by
            # installer) does too much (runs lsmod, checks for dependencies),
            # and we want to run the loop as fast as possible.
            for mod in reversed(installer_object.module_list):
                r = utils.system("rmmod %s" % (mod), ignore_status=True)
                if r <> 0:
                    raise error.TestFail("Failed to unload module %s. "
                                         "exit status: %d" % (mod, r))
    finally:
        installer_object.load_modules()
