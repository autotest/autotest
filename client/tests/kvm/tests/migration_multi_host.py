from autotest_lib.client.virt import virt_utils


def run_migration_multi_host(test, params, env):
    """
    KVM multi-host migration test:

    Migration execution progress is described in documentation
    for migrate method in class MultihostMigration.

    @param test: kvm test object.
    @param params: Dictionary with test parameters.
    @param env: Dictionary with the test environment.
    """
    class TestMultihostMigration(virt_utils.MultihostMigration):
        def __init__(self, test, params, env):
            super(TestMultihostMigration, self).__init__(test, params, env)

        def migration_scenario(self):
            srchost = self.params.get("hosts")[0]
            dsthost = self.params.get("hosts")[1]
            vms = params.get("vms").split()

            self.migrate_wait(vms, srchost, dsthost)

    mig = TestMultihostMigration(test, params, env)
    mig.run()
