from autotest_lib.server import test
from autotest_lib.client.common_lib import error

class verify_test(test.test):
    version = 1

    def execute(self, host):
        try:
            host.verify()
        except Exception, e:
            raise error.TestError("Verify failed: " + str(e))
