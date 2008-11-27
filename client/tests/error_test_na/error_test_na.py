from autotest_lib.client.common_lib import error
from autotest_lib.client.bin import test

class error_test_na(test.test):
    version = 1


    def execute(self):
        raise error.TestNAError("This test can't run on this host.")
