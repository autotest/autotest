import time
from autotest_lib.server import test

class sleeptest(test.test):
    version = 1

    def execute(self, seconds=1):
        time.sleep(seconds)
