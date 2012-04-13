import time
from autotest.server import test
from autotest.client.common_lib import error

class reinstall(test.test):
    version = 1

    def execute(self, host):
        try:
            host.machine_install()
        except Exception, e:
            raise error.TestFail(str(e))
