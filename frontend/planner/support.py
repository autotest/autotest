import common
from autotest_lib.frontend.afe import model_attributes as afe_model_attributes

class TestPlanController(object):
    """
    Allows a TestPlanSupport to manage the test plan.

    Contains the variables that the TestPlanSupport methods can manipulate, as
    well as methods for controlling the flow of the test plan.
    """
    def __init__(self, machine, test_alias, *args, **kwargs):
        super(TestPlanController, self).__init__(*args, **kwargs)
        self.machine = machine
        self.test_alias = test_alias

        self._skip = False
        self._fail = None
        self._unblock = False

        self._reboot_before = afe_model_attributes.RebootBefore.IF_DIRTY
        self._reboot_after = afe_model_attributes.RebootAfter.ALWAYS
        self._run_verify = None


    def skip_test(self):
        """
        Call this in execute_before() to skip the current test.
        """
        self._skip = True


    def fail_test(self, reason, attributes={}):
        """
        Fails the test with the reason and optional attributes provided.

        Call this in execute_before() to force the test to fail, setting the
        reason to the provided reason. You may optionally specify some test
        attributes to set as well, as a dictionary.
        """
        self._fail = (reason, attributes)


    def unblock(self):
        """
        Call this in execute_after() to keep the host unblocked.

        Hosts will block by default if a test fails. If this has been called,
        the host will be unblocked and will continue in the plan.

        You do not need to call this method for the test plan to continue if the
        test succeeded. Calling this method from a successful run has no effect.
        """
        self._unblock = True


    def set_reboot_before(self, reboot_before):
        """
        Sets the upcoming job's "Reboot Before" option.

        Must be a value from the RebootBefore frontend model attributes.
        Defaults to IF_DIRTY.
        """
        assert reboot_before in afe_model_attributes.RebootBefore.values
        self._reboot_before = reboot_before


    def set_reboot_after(self, reboot_after):
        """
        Sets the upcoming job's "Reboot After" option.

        Must be a value from the RebootAfter frontend model attributes.
        Defaults to ALWAYS.
        """
        assert reboot_after in afe_model_attributes.RebootAfter.values
        self._reboot_after = reboot_after


    def set_run_verify(self, run_verify):
        """
        Sets whether or not the job should run the verify_test.

        Defaults to True.
        """
        self._run_verify = run_verify
