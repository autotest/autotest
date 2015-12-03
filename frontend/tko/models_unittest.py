#!/usr/bin/python

import unittest
try:
    import autotest.common as common  # pylint: disable=W0611
except ImportError:
    import common  # pylint: disable=W0611
from autotest.frontend import setup_django_environment  # pylint: disable=W0611
from autotest.frontend import test_utils
from autotest.frontend.tko import models


class IterationAttributeTest(unittest.TestCase,
                             test_utils.FrontendTestMixin):

    def setUp(self):
        self._frontend_common_setup()

    def tearDown(self):
        self._frontend_common_teardown()

    def _create_test(self):
        machine = models.Machine.objects.create(hostname='foo.bar')
        job = models.Job.objects.create(tag='unittest.iterationattribute',
                                        label='foo',
                                        username='debug_user',
                                        machine=machine)
        kernel = models.Kernel.objects.create(kernel_hash='UNKNOWN',
                                              base='UNKNOWN',
                                              printable='UNKNOWN')
        status = models.Status.objects.get(word='GOOD')
        test = models.Test.objects.create(job=job,
                                          test='unittest',
                                          kernel=kernel,
                                          status=status,
                                          machine=machine)
        return test

    def test_single_attributes_for_one_test(self):
        """
        Test setting a single iteration attribute for a test

        This test, besides being what's obvious, also serves as a reminder:

        Now that Django/south creates the database schema, whatever is set in
        the models is respected, that is, no "fake tricks" go unpunished.

        The net effect is that a bug appears when trying to add multiple
        attributes/results to tko_iteration_attributes/tko_iteration_results.
        """
        test = self._create_test()
        iteration_attr = models.IterationAttribute.objects.create(
            test=test,
            iteration=1,
            attribute='attribute',
            value='value')
        iteration_attr.delete()
        test.delete()


if __name__ == '__main__':
    unittest.main()
