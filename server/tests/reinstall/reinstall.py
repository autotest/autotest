import time
from autotest.server import test
from autotest.client.shared import error

class reinstall(test.test):
    version = 1

    def execute(self, host):
        try:
            host.machine_install()
        except Exception, e:
            raise error.TestFail(str(e))
