import sys, os, time, shelve, resource, logging, cPickle
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error


class test_routine:
    def __init__(self, module_name, routine_name):
        self.module_name = module_name
        self.routine_name = routine_name
        self.routine = None


def dump_env(obj, filename):
    file = open(filename, "w")
    cPickle.dump(obj, file)
    file.close()


def load_env(filename, default=None):
    try:
        file = open(filename, "r")
    except:
        return default
    obj = cPickle.load(file)
    file.close()
    return obj


class kvm(test.test):
    """
    Suite of KVM virtualization functional tests.
    Contains tests for testing both KVM kernel code and userspace code.

    @copyright: Red Hat 2008-2009
    @author: Uri Lublin (uril@redhat.com)
    @author: Dror Russo (drusso@redhat.com)
    @author: Michael Goldish (mgoldish@redhat.com)
    @author: David Huff (dhuff@redhat.com)
    @author: Alexey Eromenko (aeromenk@redhat.com)
    @author: Mike Burns (mburns@redhat.com)

    @see: http://www.linux-kvm.org/page/KVM-Autotest/Client_Install
            (Online doc - Getting started with KVM testing)
    """
    version = 1
    def initialize(self):
        # Define the test routines corresponding to different values
        # of the 'type' field
        self.test_routines = {
                # type                       module name            routine
                "build":        test_routine("build", "run_build"),
                "steps":        test_routine("steps", "run_steps"),
                "stepmaker":    test_routine("stepmaker", "run_stepmaker"),
                "boot":         test_routine("kvm_tests", "run_boot"),
                "shutdown":     test_routine("kvm_tests", "run_shutdown"),
                "migration":    test_routine("kvm_tests", "run_migration"),
                "yum_update":   test_routine("kvm_tests", "run_yum_update"),
                "autotest":     test_routine("kvm_tests", "run_autotest"),
                "linux_s3":     test_routine("kvm_tests", "run_linux_s3"),
                "stress_boot":  test_routine("kvm_tests", "run_stress_boot"),
                "timedrift":    test_routine("kvm_tests", "run_timedrift"),
                "autoit":       test_routine("kvm_tests", "run_autoit"),
                }

        # Make it possible to import modules from the test's bindir
        sys.path.append(self.bindir)


    def run_once(self, params):
        import logging
        import kvm_utils
        import kvm_preprocessing

        # Enable core dumps
        resource.setrlimit(resource.RLIMIT_CORE, (-1, -1))

        # Report the parameters we've received and write them as keyvals
        logging.debug("Test parameters:")
        keys = params.keys()
        keys.sort()
        for key in keys:
            logging.debug("    %s = %s", key, params[key])
            self.write_test_keyval({key: params[key]})

        # Open the environment file
        env_filename = os.path.join(self.bindir, params.get("env", "env"))
        env = load_env(env_filename, {})
        logging.debug("Contents of environment: %s" % str(env))

        try:
            try:
                # Get the test routine corresponding to the specified test type
                type = params.get("type")
                routine_obj = self.test_routines.get(type)
                # If type could not be found in self.test_routines...
                if not routine_obj:
                    message = "Unsupported test type: %s" % type
                    logging.error(message)
                    raise error.TestError(message)
                # If we don't have the test routine yet...
                if not routine_obj.routine:
                    # Dynamically import the module
                    module = __import__(routine_obj.module_name)
                    # Get the needed routine
                    routine_name = "module." + routine_obj.routine_name
                    routine_obj.routine = eval(routine_name)

                # Preprocess
                kvm_preprocessing.preprocess(self, params, env)
                dump_env(env, env_filename)
                # Run the test function
                routine_obj.routine(self, params, env)
                dump_env(env, env_filename)

            except Exception, e:
                logging.error("Test failed: %s", e)
                logging.debug("Postprocessing on error...")
                kvm_preprocessing.postprocess_on_error(self, params, env)
                dump_env(env, env_filename)
                raise

        finally:
            # Postprocess
            kvm_preprocessing.postprocess(self, params, env)
            logging.debug("Contents of environment: %s", str(env))
            dump_env(env, env_filename)
