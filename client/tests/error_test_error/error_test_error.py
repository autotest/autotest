from autotest_lib.client.common_lib import error
from autotest_lib.client import test

class error_test_error(test.test):
    version = 1


    def execute(self):
        raise error.TestError("This test always causes an error.")
