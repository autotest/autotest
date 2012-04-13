from autotest.client.common_lib import error
from autotest.client import test

class aborttest(test.test):
    version = 1

    def execute(self):
        raise error.JobError('Arrrrrrrrggggh. You are DOOOMED')
