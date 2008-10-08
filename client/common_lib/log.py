import sys, re, traceback


job_statuses = ["TEST_NA", "ABORT", "ERROR", "FAIL", "WARN", "GOOD", "ALERT",
                "RUNNING", "NOSTATUS"]

def is_valid_status(status):
    if not re.match(r'(START|INFO|(END )?('+'|'.join(job_statuses)+'))$',
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


def log_and_ignore_errors(msg):
    """ A decorator for wrapping functions in a 'log exception and ignore'
    try-except block. """
    def decorator(fn):
        def decorated_func(*args, **dargs):
            try:
                fn(*args, **dargs)
            except Exception:
                print msg
                traceback.print_exc(file=sys.stdout)
        return decorated_func
    return decorator
