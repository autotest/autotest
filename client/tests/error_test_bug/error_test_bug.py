from autotest.client.common_lib import error
from autotest.client import test

class error_test_bug(test.test):
    version = 1


    def execute(self):
        raise RuntimeError("Woof Woof, Timmy's trapped in the well!")
