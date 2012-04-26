from autotest.client.shared import error
from autotest.client import test

class aborttest(test.test):
    version = 1

    def execute(self):
        raise error.JobError('Arrrrrrrrggggh. You are DOOOMED')
