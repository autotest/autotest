from autotest.client.shared import error
from autotest.client import test

class error_test_error(test.test):
    version = 1


    def execute(self):
        raise error.TestError("This test always causes an error.")
