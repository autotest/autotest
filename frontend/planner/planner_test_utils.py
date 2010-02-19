import common
from autotest_lib.frontend.afe import frontend_test_utils
from autotest_lib.frontend.afe import models as afe_models
from autotest_lib.frontend.planner import models
from autotest_lib.client.common_lib import utils

class PlannerTestMixin(frontend_test_utils.FrontendTestMixin):
    _PLAN_NAME = 'plan'

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
