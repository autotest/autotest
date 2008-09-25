import os, sys, datetime


_debug_logger = sys.stderr
def dprint(msg):
    print >> _debug_logger, msg


def redirect_parser_debugging(ostream):
    global _debug_logger
    _debug_logger = ostream


def get_timestamp(mapping, field):
    val = mapping.get(field, None)
    if val is not None:
        val = datetime.datetime.fromtimestamp(int(val))
    return val


def find_toplevel_job_dir(start_dir):
    """ Starting from start_dir and moving upwards, find the top-level
    of the job results dir. We can't just assume that it corresponds to
    the actual job.dir, because job.dir may just be a subdir of the "real"
    job dir that autoserv was launched with. Returns None if it can't find
    a top-level dir. """
    job_dir = start_dir
    while not os.path.exists(os.path.join(job_dir, ".autoserv_execute")):
        if job_dir == "/":
            return None
        job_dir = os.path.dirname(job_dir)
    return job_dir
