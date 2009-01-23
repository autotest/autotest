from autotest_lib.server import test
from autotest_lib.client.common_lib import error

class cleanup_test(test.test):
    version = 1

    def execute(self, host):
        try:
            host.cleanup()
        except Exception, e:
            raise error.TestError("Cleanup failed: " + str(e))
