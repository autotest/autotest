import os
from autotest_lib.client.common_lib import utils, error
from autotest_lib.client.common_lib import boottool as common_boottool

class boottool(common_boottool.boottool):
    def __init__(self, boottool_exec=None):
        super(boottool, self).__init__()

        if boottool_exec:
            self._boottool_exec = boottool_exec
        else:
            autodir = os.environ['AUTODIR']
            self._boottool_exec = autodir + '/tools/boottool'

        if not self._boottool_exec:
            raise error.AutotestError('Failed to set boottool_exec')


    def _run_boottool(self, *options):
        return utils.system_output(self._boottool_exec, args=options)
