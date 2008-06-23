"""\
Logging helper tools.
"""

import re

__author__ = 'jadmanski@google.com (John Admanski)'


job_statuses = ["TEST_NA", "ABORT", "ERROR", "FAIL", "WARN", "GOOD", "ALERT",
                "NOSTATUS"]

def is_valid_status(status):
    if not re.match(r'(START|(END )?('+'|'.join(job_statuses)+'))$',
                    status):
        return False
    else:
        return True


def record(fn):
    """
    Generic method decorator for logging calls under the
    assumption that return=GOOD, exception=FAIL. The method
    determines parameters as:
            subdir = self.subdir if it exists, or None
            operation = "class name"."method name"
            status = None on GOOD, str(exception) on FAIL
    The object using this method must have a job attribute
    for the logging to actually occur, otherwise the logging
    will silently fail.

    Logging can explicitly be disabled for a call by passing
    a logged=False parameter
    """
    def recorded_func(self, *args, **dargs):
        logged = dargs.pop('logged', True)
        job = getattr(self, 'job', None)
        # if logging is disabled/unavailable, just
        # call the method
        if not logged or job is None:
            return fn(self, *args, **dargs)
        # logging is available, so wrap the method call
        # in success/failure logging
        subdir = getattr(self, 'subdir', None)
        operation = '%s.%s' % (self.__class__.__name__,
                               fn.__name__)
        try:
            result = fn(self, *args, **dargs)
            job.record('GOOD', subdir, operation)
        except Exception, detail:
            job.record('FAIL', subdir, operation, str(detail))
            raise
        return result
    return recorded_func
