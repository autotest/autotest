from autotest_lib.client.bin import base_sysinfo
try:
    from autotest_lib.client.bin import site_sysinfo
except ImportError:
    # no site_sysinfo, just make a class using the base version
    class sysinfo(base_sysinfo.base_sysinfo):
        pass
else:
    # otherwise, use the site version (should inherit from the base)
    class sysinfo(site_sysinfo.site_sysinfo):
        pass

# pull in some data stucture stubs from base_sysinfo, for convenience
logfile = base_sysinfo.logfile
command = base_sysinfo.command
