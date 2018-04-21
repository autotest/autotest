import os
import re

from autotest.frontend import setup_django_environment  # pylint: disable=W0611
from autotest.frontend.tko import models as tko_models
from autotest.frontend.tko import models_utils as tko_models_utils
from autotest.tko import utils


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
    # as differentiator.
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
        insert_patch(tko_kernel, patch)

    return tko_kernel


def insert_test(job, test, tko_job=None, tko_machine=None):
    tko_kernel = insert_kernel(test.kernel)
    status = tko_models.Status.objects.get(word=test.status)

    if tko_job is None:
        tko_job = tko_models_utils.job_get_by_idx(job.index)

    if tko_machine is None:
        tko_machine = tko_models_utils.machine_get_by_idx(job.machine_idx)

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
        tko_test.save()
        test.test_idx = tko_test.test_idx

    for i in test.iterations:
        for key, value in i.attr_keyval.items():
            tko_models.IterationAttribute.objects.create(
                test=tko_test,
                attribute=key,
                iteration=i.index,
                value=value)

        for key, value in i.perf_keyval.items():
            tko_models.IterationResult.objects.create(
                test=tko_test,
                iteration=i.index,
                attribute=key,
                value=value)

    for key, value in test.attributes.items():
        tko_models.TestAttribute.objects.create(
            test=tko_test,
            attribute=key,
            value=value)

    for label_index in test.labels:
        label = tko_models_utils.test_label_get_by_idx(label_index)
        if label is not None:
            label.tests.append(tko_test)


def insert_job(jobname, job):
    # write the job into the database
    machine = tko_models_utils.machine_create(job.machine,
                                              job.machine_group,
                                              job.machine_owner)

    # Update back machine index, used by some legacy code
    machine.save()
    job.machine_idx = machine.pk

    afe_job_id = utils.get_afe_job_id(jobname)
    if not afe_job_id:
        afe_job_id = None

    tko_job_data = {
        'tag': jobname,
        'label': job.label,
        'machine': machine,
        'queued_time': job.queued_time,
        'started_time': job.started_time,
        'finished_time': job.finished_time,
        'afe_job_id': afe_job_id
    }

    job_already_exists = hasattr(job, 'index')
    if job_already_exists:
        tko_models.Job.objects.filter(pk=job.index).update(**tko_job_data)
        tko_job = tko_models.Job.objects.get(pk=job.index)
    else:
        tko_job = tko_models.Job.objects.create(**tko_job_data)

    # Update back the index of the job object, used by some legacy code
    tko_job.save()
    job.index = tko_job.pk

    # update job keyvals
    for key, value in job.keyval_dict.items():
        # We find or create using job and key only
        job_keyval, created = tko_models.JobKeyval.objects.get_or_create(
            job=tko_job,
            key=key)
        # and now we have to update with value
        job_keyval.value = value
        job_keyval.save()

    # now insert the tests
    for test in job.tests:
        insert_test(job, test, tko_job, machine)
