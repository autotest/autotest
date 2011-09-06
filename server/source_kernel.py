# Copyright 2007 Google Inc. Released under the GPL v2

"""
This module defines the SourceKernel class

        SourceKernel: an linux kernel built from source
"""


from autotest_lib.server import kernel, autotest


class SourceKernel(kernel.Kernel):
    """
    This class represents a linux kernel built from source.

    It is used to obtain a built kernel or create one from source and
    install it on a Host.

    Implementation details:
    This is a leaf class in an abstract class hierarchy, it must
    implement the unimplemented methods in parent classes.
    """
    def __init__(self, k):
        super(SourceKernel, self).__init__()
        self.__kernel = k
        self.__patch_list = []
        self.__config_file = None
        self.__autotest = autotest.Autotest()


    def configure(self, configFile):
        self.__config_file = configFile


    def patch(self, patchFile):
        self.__patch_list.append(patchFile)


    def build(self, host):
        ctlfile = self.__control_file(self.__kernel, self.__patch_list,
                                    self.__config_file)
        self.__autotest.run(ctlfile, host.get_tmp_dir(), host)


    def install(self, host):
        self.__autotest.install(host)
        ctlfile = ("testkernel = job.kernel('%s')\n"
                   "testkernel.install()\n"
                   "testkernel.add_to_bootloader()\n" %(self.__kernel))
        self.__autotest.run(ctlfile, host.get_tmp_dir(), host)


    def __control_file(self, kernel, patch_list, config):
        ctl = ("testkernel = job.kernel('%s')\n" % kernel)

        if len(patch_list):
            patches = ', '.join(["'%s'" % x for x in patch_list])
            ctl += "testkernel.patch(%s)\n" % patches

        if config:
            ctl += "testkernel.config('%s')\n" % config
        else:
            ctl += "testkernel.config('', None, True)\n"

        ctl += "testkernel.build()\n"

        # copy back to server

        return ctl
