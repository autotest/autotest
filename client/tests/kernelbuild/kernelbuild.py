from autotest_lib.client.bin import test, kernel


class kernelbuild(test.test):
    version = 1

    def execute(self, base_tree, patches, config, config_list = None):
        kernel = self.job.kernel(base_tree, self.outputdir)
        if patches:
            kernel.patch(*patches)
        kernel.config(config, config_list)

        kernel.build()
