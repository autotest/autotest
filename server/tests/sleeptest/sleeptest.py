import time
from autotest_lib.client.bin import test

class sleeptest(test.test):
    version = 1

    def execute(self, seconds = 1):
        time.sleep(seconds)
