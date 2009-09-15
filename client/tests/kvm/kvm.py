import sys, os, time, logging
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
    def initialize(self):
        # Make it possible to import modules from the test's bindir
        sys.path.append(self.bindir)
        self.subtest_dir = os.path.join(self.bindir, 'tests')


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
                type = params.get("type")
                # Verify if we have the correspondent source file for it
                module_path = os.path.join(self.subtest_dir, '%s.py' % type)
                if not os.path.isfile(module_path):
                    raise error.TestError("No %s.py test file found" % type)
                # Load the tests directory (which was turned into a py module)
                try:
                    test_module = __import__("tests.%s" % type)
                except ImportError, e:
                    raise error.TestError("Failed to import test %s: %s" %
                                          (type, e))

                # Preprocess
                kvm_preprocessing.preprocess(self, params, env)
                kvm_utils.dump_env(env, env_filename)
                # Run the test function
                eval("test_module.%s.run_%s(self, params, env)" % (type, type))
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
