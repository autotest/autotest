import os

from autotest.tko import utils
from autotest.frontend import setup_django_environment
from autotest.frontend.tko import models_utils as tko_models_utils
from autotest.frontend.tko import models as tko_models


def insert_patch(tko_kernel, patch):
    name = os.path.basename(patch.reference)[:80]
    tko_patch, created = tko_models.Patch.objects.get_or_create(
        kernel=tko_kernel,
        name=name,
        url=patch.reference,
        hash=patch.hash)
    return tko_patch


def insert_kernel(kernel):
    tko_kernel, created = tko_models.Kernel.objects.get_or_create(
        kernel_hash=kernel.kernel_hash)

    if not created:
        return tko_kernel

    tko_kernel.base = kernel.base
    tko_kernel.printable = kernel.base

    # If this kernel has any significant patches, append their hash
    # as diferentiator.
    patch_count = 0
    for patch in kernel.patches:
        match = re.match(r'.*(-mm[0-9]+|-git[0-9]+)\.(bz2|gz)$',
                         patch.reference)
        if not match:
            patch_count += 1

    if patch_count > 0:
        tko_kernel.printable = '%s p%d' % (tko_kernel.printable,
                                           tko_kernel.kernel_idx)

    for patch in kernel.patches:
        self.insert_patch(tko_kernel, patch)

    return tko_kernel

def insert_test(job, test, tko_job, tko_machine):
    tko_kernel = insert_kernel(test.kernel)
    status = tko_models.Status.objects.get(word=test.status)

    subdir = test.subdir
    if test.subdir is None:
        subdir = ''

    tko_test_data = {
        'job': tko_job,
        'test': test.testname,
        'subdir': subdir,
        'kernel': tko_kernel,
        'status': status,
        'reason': test.reason,
        'machine': tko_machine,
        'started_time': test.started_time,
        'finished_time': test.finished_time
        }

    test_already_exists = hasattr(test, "test_idx")
    if test_already_exists:
        tko_models.Test.objects.filter(pk=test.test_idx).update(**tko_test_data)
        tko_test = tko_models.Test.objects.get(pk=test.test_idx)

        # clean up iteration result/attributes and test attributes that will
        # be re-added shortly
        tko_models.IterationResult.objects.filter(
            test=test.test_idx).delete()
        tko_models.IterationAttribute.objects.filter(
            test=test.test_idx).delete()
        tko_models.TestAttribute.objects.filter(test=test.test_idx,
                                                user_created=False).delete()

    else:
        tko_test = tko_models.Test.objects.create(**tko_test_data)

    for i in test.iterations:
        for key, value in i.attr_keyval.iteritems():
            tko_models.IterationAttribute.objects.create(
                test=tko_test,
                attribute=key,
                iteration=i.index,
                value=value)

        for key, value in i.perf_keyval.iteritems():
            tko_models.IterationResult.objects.create(
                test=tko_test,
                iteration=i.index,
                attribute=key,
                value=value)

    for key, value in test.attributes.iteritems():
        tko_models.TestAttribute.objects.create(
            test=tko_test,
            attribute=key,
            value=value)

    # WARNING: there's a possible regression of functionality on this code!
    # I can not find anywhere where the test labels are parsed into the
    # test objects. The original parsing of the test labels is done by
    # index and direct manipulation of the many-to-many table. The way
    # to do this via Django ORM wouble to create TestLabel() instances
    # and add the test to the 'tests' member. Unfortunately, without
    # the label data such as name and description, it's not possible
    # to instantiate TestLabel()s in the first place.


def insert_job(jobname, job):
    # write the job into the database
    machine = tko_models_utils.machine_create(job.machine,
                                              job.machine_group,
                                              job.machine_owner)

    afe_job_id = utils.get_afe_job_id(jobname)
    if not afe_job_id:
        afe_job_id = None

    tko_job_data = {
        'tag' : jobname,
        'label' : job.label,
        'machine' : machine,
        'queued_time' : job.queued_time,
        'started_time' : job.started_time,
        'finished_time' : job.finished_time,
        'afe_job_id' : afe_job_id
        }

    job_already_exists = hasattr(job, 'index')
    if job_already_exists:
        tko_models.Job.objects.filter(pk=job.index).update(**tko_job_data)
        tko_job = tko_models.Job.objects.get(pk=job.index)
    else:
        tko_job = tko_models.Job.objects.create(**tko_job_data)

    # update job keyvals
    for key, value in job.keyval_dict.iteritems():
        # We find or create using job and key only
        job_keyval, created = tko_models.JobKeyval.objects.get_or_create(
            job=tko_job,
            key=key)
        # and now we have to update with value
        job_keyval.value = value
        job_keyval.save()

    # now insert the tests, conver the following block of code
    for test in job.tests:
        insert_test(job, test, tko_job, machine)
