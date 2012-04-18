import time
from autotest.server import test

class sleeptest(test.test):
    version = 1

    def run_once(self, host=None, seconds=1):
        time.sleep(seconds)
