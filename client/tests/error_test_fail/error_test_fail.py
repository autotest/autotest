from autotest_lib.client.common_lib import error
from autotest_lib.client import test

class error_test_fail(test.test):
    version = 1


    def execute(self):
        raise error.TestFail("This test always fails.")
