from autotest_lib.client.bin import test

class error_cleanup(test.test):
    version = 1


    def execute(self):
        pass


    def cleanup(self):
        raise NameError("test a bug in cleanup()")
