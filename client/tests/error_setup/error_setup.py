from autotest_lib.client import test

class error_setup(test.test):
    version = 1


    def setup(self):
        raise ValueError("test a bug in setup()")

    def execute(self):
        pass
