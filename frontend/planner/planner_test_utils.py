import common
from autotest_lib.frontend.afe import frontend_test_utils
from autotest_lib.frontend.afe import models as afe_models
from autotest_lib.frontend.tko import models as tko_models
from autotest_lib.frontend.planner import models
from autotest_lib.client.common_lib import utils

class PlannerTestMixin(frontend_test_utils.FrontendTestMixin):
    _PLAN_NAME = 'plan'
    GOOD_STATUS_WORD = 'GOOD'
    RUNNING_STATUS_WORD = 'RUNNING'
    FAIL_STATUS_WORD = 'FAIL'

    def _planner_common_setup(self):
        self._frontend_common_setup()

        plan = models.Plan.objects.create(name=self._PLAN_NAME)
        models.Host.objects.create(
                plan=plan, host=afe_models.Host.objects.get(hostname='host1'))
        models.Host.objects.create(
                plan=plan, host=afe_models.Host.objects.get(hostname='host2'))
        plan.host_labels.add(afe_models.Label.objects.get(name='label1'))
        plan.save()

        self._plan = plan


    def _planner_common_teardown(self):
        self._plan.delete()
        self._frontend_common_teardown()


    def _setup_active_plan(self):
        """
        Create an active test plan

        Sets up all the infrastructure for a active test plan. Stores the
        following in self:

        _hostname: hostname of the machine under test
        _control: the models.ControlFile object
        _test_config: the models.TestConfig object
        _afe_job: the AFE job started by the plan
        _planner_host: the models.Host object
        _planner_job: the models.Job object
        _tko_machine: the TKO machine (as a tko_models.Machine object) for the
                      results
        _tko_job: the TKO job (as a tko_models.Job object) for the results
        _tko_kernel: the TKO kernel (as a tko_models.Kernel object) associated
                     with the TKO machine
        _running_status: the TKO status (as a tko_models.Status object) that
                         indicates a running TKO test
        _good_status: the TKO status (as a tko_models.Status object) that
                      indicates a completed and passed TKO test
        """
        self._hostname = self.hosts[0].hostname
        self._control, _ = models.ControlFile.objects.get_or_create(
                contents='test_control')
        self._test_config = models.TestConfig.objects.create(
                plan=self._plan, alias='config', control_file=self._control,
                execution_order=1, estimated_runtime=1)
        self._afe_job = self._create_job(hosts=(1,))
        self._planner_host = self._plan.host_set.get(host=self.hosts[0])
        self._planner_job = models.Job.objects.create(
                plan=self._plan, test_config=self._test_config,
                afe_job=self._afe_job)
        self._tko_machine = tko_models.Machine.objects.create(
                hostname=self._hostname)
        self._tko_job = tko_models.Job.objects.create(
                tag='job', machine=self._tko_machine,
                afe_job_id=self._afe_job.id)
        self._tko_kernel = tko_models.Kernel.objects.create()
        self._running_status = tko_models.Status.objects.create(
                word=self.RUNNING_STATUS_WORD)
        self._good_status = tko_models.Status.objects.create(
                word=self.GOOD_STATUS_WORD)
        self._fail_status = tko_models.Status.objects.create(
                word=self.FAIL_STATUS_WORD)
