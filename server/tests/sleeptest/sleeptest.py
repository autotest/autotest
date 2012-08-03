import time
from autotest.server import test

class sleeptest(test.test):
    version = 1

    def execute(self, host, seconds=1):
        host.run('sleep ' + str(seconds))
