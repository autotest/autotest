from autotest.server import test
from autotest.client.shared import error

class verify_test(test.test):
    version = 1

    def execute(self, host):
        try:
            host.verify()
        except Exception, e:
            raise error.TestError("Verify failed: " + str(e))
