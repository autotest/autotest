from autotest.client import base_sysinfo
from autotest.client.shared import utils

sysinfo = utils.import_site_class(__file__,
                                  "autotest.client.site_sysinfo",
                                  "site_sysinfo", base_sysinfo.base_sysinfo)

# pull in some data structure stubs from base_sysinfo, for convenience
logfile = base_sysinfo.logfile
command = base_sysinfo.command
