import sys, os, time, logging, imp
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
import kvm_utils, kvm_preprocessing


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
    def run_once(self, params):
        # Report the parameters we've received and write them as keyvals
        logging.debug("Test parameters:")
        keys = params.keys()
        keys.sort()
        for key in keys:
            logging.debug("    %s = %s", key, params[key])
            self.write_test_keyval({key: params[key]})

        # Open the environment file
        env_filename = os.path.join(self.bindir, params.get("env", "env"))
        env = kvm_utils.load_env(env_filename, {})
        logging.debug("Contents of environment: %s" % str(env))

        try:
            try:
                # Get the test routine corresponding to the specified test type
                t_type = params.get("type")
                # Verify if we have the correspondent source file for it
                subtest_dir = os.path.join(self.bindir, "tests")
                module_path = os.path.join(subtest_dir, "%s.py" % t_type)
                if not os.path.isfile(module_path):
                    raise error.TestError("No %s.py test file found" % t_type)
                # Load the test module
                f, p, d = imp.find_module(t_type, [subtest_dir])
                test_module = imp.load_module(t_type, f, p, d)
                f.close()

                # Preprocess
                kvm_preprocessing.preprocess(self, params, env)
                kvm_utils.dump_env(env, env_filename)
                # Run the test function
                run_func = getattr(test_module, "run_%s" % t_type)
                run_func(self, params, env)
                kvm_utils.dump_env(env, env_filename)

            except Exception, e:
                logging.error("Test failed: %s", e)
                logging.debug("Postprocessing on error...")
                kvm_preprocessing.postprocess_on_error(self, params, env)
                kvm_utils.dump_env(env, env_filename)
                raise

        finally:
            # Postprocess
            kvm_preprocessing.postprocess(self, params, env)
            logging.debug("Contents of environment: %s", str(env))
            kvm_utils.dump_env(env, env_filename)
