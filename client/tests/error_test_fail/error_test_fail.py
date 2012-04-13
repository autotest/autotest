from autotest.client.shared import error
from autotest.client import test

class error_test_fail(test.test):
    version = 1


    def execute(self):
        raise error.TestFail("This test always fails.")
