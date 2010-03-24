from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
import re

class hwclock(test.test):
    version = 1

    def run_once(self, seconds=1):
        utils.system('/sbin/hwclock --set --date "2/2/80 03:04:00"')
        date = utils.system_output('/sbin/hwclock')
        if not re.match('Sat *Feb *2 *03:04:.. 1980', date):
            raise error.TestFail('Failed to set hwclock back to the eighties')


    def cleanup(self):
        utils.system('/sbin/hwclock --systohc --noadjfile --utc')
