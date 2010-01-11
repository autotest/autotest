from autotest_lib.client.common_lib import utils
from autotest_lib.client.bin import base_sysinfo

sysinfo = utils.import_site_class(__file__,
                                  "autotest_lib.client.bin.site_sysinfo",
                                  "site_sysinfo", base_sysinfo.base_sysinfo)

# pull in some data stucture stubs from base_sysinfo, for convenience
logfile = base_sysinfo.logfile
command = base_sysinfo.command
