from autotest_lib.frontend.shared import query_lib, resource_lib
from autotest_lib.frontend.tko import models

class TestResult(resource_lib.InstanceEntry):
    model = models.Test


    @classmethod
    def add_query_selectors(cls, query_processor):
        query_processor.add_field_selector('afe_job_id',
                                           field='job__afe_job_id')
        query_processor.add_keyval_selector('has_keyval', models.TestAttribute,
                                            'attribute', 'value')


    @classmethod
    def from_uri_args(cls, request, test_id, **kwargs):
        return cls(request, models.Test.objects.get(pk=test_id))


    def _uri_args(self):
        return {'test_id': self.instance.pk}


    def short_representation(self):
        rep = super(TestResult, self).short_representation()
        rep.update(id=self.instance.test_idx,
                   test_name=self.instance.test,
                   status=self.instance.status.word,
                   reason=self.instance.reason,
                   afe_job_id=self.instance.job.afe_job_id,
                   )
        return rep


    def full_representation(self):
        rep = super(TestResult, self).full_representation()
        rep['keyvals'] = dict((keyval.attribute, keyval.value)
                              for keyval
                              in self.instance.testattribute_set.all())
        return rep


class TestResultCollection(resource_lib.Collection):
    queryset = models.Test.objects.order_by('-test_idx')
    entry_class = TestResult


class ResourceDirectory(resource_lib.Resource):
    _permitted_methods = ('GET',)

    def handle_request(self):
        result = self.link()
        result.update({
                'test_results': TestResultCollection(self._request).link(),
                })
        return self._basic_response(result)
