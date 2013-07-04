"""
Simple utility wrappers around the AFE models
"""

from autotest.frontend.afe.models import Job


def job_get_by_id(job_id):
    '''
    Return a job based on its id
    '''
    try:
        job = Job.objects.get(pk=job_id)
        return job
    except Job.DoesNotExist:
        return None


def job_delete_by_id(job_id):
    '''
    Deletes a job entry based on its tag
    '''
    Job.objects.get(pk=job_id).delete()
    return job_get_by_id(job_id) is None
