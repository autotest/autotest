#!/usr/bin/python -u

import os, sys, optparse, fcntl, errno, traceback, socket

try:
    import autotest.common as common
except ImportError:
    import common
from autotest.client.common_lib import mail, pidfile
from autotest.tko import db as tko_db, utils as tko_utils, status_lib, models
from autotest.client.common_lib import utils


def parse_args():
    # build up our options parser and parse sys.argv
    parser = optparse.OptionParser()
    parser.add_option("-m", help="Send mail for FAILED tests",
                      dest="mailit", action="store_true")
    parser.add_option("-r", help="Reparse the results of a job",
                      dest="reparse", action="store_true")
    parser.add_option("-o", help="Parse a single results directory",
                      dest="singledir", action="store_true")
    parser.add_option("-l", help=("Levels of subdirectories to include "
                                  "in the job name"),
                      type="int", dest="level", default=1)
    parser.add_option("-n", help="No blocking on an existing parse",
                      dest="noblock", action="store_true")
    parser.add_option("-s", help="Database server hostname",
                      dest="db_host", action="store")
    parser.add_option("-u", help="Database username", dest="db_user",
                      action="store")
    parser.add_option("-p", help="Database password", dest="db_pass",
                      action="store")
    parser.add_option("-d", help="Database name", dest="db_name",
                      action="store")
    parser.add_option("--write-pidfile",
                      help="write pidfile (.parser_execute)",
                      dest="write_pidfile", action="store_true",
                      default=False)
    options, args = parser.parse_args()

    # we need a results directory
    if len(args) == 0:
        tko_utils.dprint("ERROR: at least one results directory must "
                         "be provided")
        parser.print_help()
        sys.exit(1)

    # pass the options back
    return options, args


def format_failure_message(jobname, kernel, testname, status, reason):
    format_string = "%-12s %-20s %-12s %-10s %s"
    return format_string % (jobname, kernel, testname, status, reason)


def mailfailure(jobname, job, message):
    message_lines = [""]
    message_lines.append("The following tests FAILED for this job")
    message_lines.append("http://%s/results/%s" %
                         (socket.gethostname(), jobname))
    message_lines.append("")
    message_lines.append(format_failure_message("Job name", "Kernel",
                                                "Test name", "FAIL/WARN",
                                                "Failure reason"))
    message_lines.append(format_failure_message("=" * 8, "=" * 6, "=" * 8,
                                                "=" * 8, "=" * 14))
    message_header = "\n".join(message_lines)

    subject = "AUTOTEST: FAILED tests from job %s" % jobname
    mail.send("", job.user, "", subject, message_header + message)


def parse_one(db, jobname, path, reparse, mail_on_failure):
    """
    Parse a single job. Optionally send email on failure.
    """
    tko_utils.dprint("\nScanning %s (%s)" % (jobname, path))
    old_job_idx = db.find_job(jobname)
    # old tests is a dict from tuple (test_name, subdir) to test_idx
    old_tests = {}
    if old_job_idx is not None:
        if not reparse:
            tko_utils.dprint("! Job is already parsed, done")
            return

        raw_old_tests = db.select("test_idx,subdir,test", "tko_tests",
                                  {"job_idx": old_job_idx})
        if raw_old_tests:
            old_tests = dict(((test, subdir), test_idx)
                             for test_idx, subdir, test in raw_old_tests)

    # look up the status version
    job_keyval = models.job.read_keyval(path)
    status_version = job_keyval.get("status_version", 0)

    # parse out the job
    parser = status_lib.parser(status_version)
    job = parser.make_job(path)
    status_log = os.path.join(path, "status.log")
    if not os.path.exists(status_log):
        status_log = os.path.join(path, "status")
    if not os.path.exists(status_log):
        tko_utils.dprint("! Unable to parse job, no status file")
        return

    # parse the status logs
    tko_utils.dprint("+ Parsing dir=%s, jobname=%s" % (path, jobname))
    status_lines = open(status_log).readlines()
    parser.start(job)
    tests = parser.end(status_lines)

    # parser.end can return the same object multiple times, so filter out dups
    job.tests = []
    already_added = set()
    for test in tests:
        if test not in already_added:
            already_added.add(test)
            job.tests.append(test)

    # try and port test_idx over from the old tests, but if old tests stop
    # matching up with new ones just give up
    if reparse and old_job_idx is not None:
        job.index = old_job_idx
        for test in job.tests:
            test_idx = old_tests.pop((test.testname, test.subdir), None)
            if test_idx is not None:
                test.test_idx = test_idx
            else:
                tko_utils.dprint("! Reparse returned new test "
                                 "testname=%r subdir=%r" %
                                 (test.testname, test.subdir))
        for test_idx in old_tests.itervalues():
            where = {'test_idx' : test_idx}
            db.delete('tko_iteration_result', where)
            db.delete('tko_iteration_attributes', where)
            db.delete('tko_test_attributes', where)
            db.delete('tko_test_labels_tests', {'test_id': test_idx})
            db.delete('tko_tests', where)

    # check for failures
    message_lines = [""]
    for test in job.tests:
        if not test.subdir:
            continue
        tko_utils.dprint("* testname, status, reason: %s %s %s"
                         % (test.subdir, test.status, test.reason))
        if test.status in ("FAIL", "WARN"):
            message_lines.append(format_failure_message(
                jobname, test.kernel.base, test.subdir,
                test.status, test.reason))
    message = "\n".join(message_lines)

    # send out a email report of failure
    if len(message) > 2 and mail_on_failure:
        tko_utils.dprint("Sending email report of failure on %s to %s"
                         % (jobname, job.user))
        mailfailure(jobname, job, message)

    # write the job into the database
    db.insert_job(jobname, job)

    # Serializing job into a binary file
    try:
        from autotest.tko import tko_pb2
        from autotest.tko import job_serializer

        serializer = job_serializer.JobSerializer()
        binary_file_name = os.path.join(path, "job.serialize")
        serializer.serialize_to_binary(job, jobname, binary_file_name)

        if reparse:
            site_export_file = "autotest.tko.site_export"
            site_export = utils.import_site_function(__file__,
                                                     site_export_file,
                                                     "site_export",
                                                     _site_export_dummy)
            site_export(binary_file_name)

    except ImportError:
        tko_utils.dprint("DEBUG: tko_pb2.py doesn't exist. Create by "
                         "compiling tko/tko.proto.")

    db.commit()

def _site_export_dummy(binary_file_name):
    pass

def _get_job_subdirs(path):
    """
    Returns a list of job subdirectories at path. Returns None if the test
    is itself a job directory. Does not recurse into the subdirs.
    """
    # if there's a .machines file, use it to get the subdirs
    machine_list = os.path.join(path, ".machines")
    if os.path.exists(machine_list):
        subdirs = set(line.strip() for line in file(machine_list))
        existing_subdirs = set(subdir for subdir in subdirs
                               if os.path.exists(os.path.join(path, subdir)))
        if len(existing_subdirs) != 0:
            return existing_subdirs

    # if this dir contains ONLY subdirectories, return them
    contents = set(os.listdir(path))
    contents.discard(".parse.lock")
    subdirs = set(sub for sub in contents if
                  os.path.isdir(os.path.join(path, sub)))
    if len(contents) == len(subdirs) != 0:
        return subdirs

    # this is a job directory, or something else we don't understand
    return None


def parse_leaf_path(db, path, level, reparse, mail_on_failure):
    job_elements = path.split("/")[-level:]
    jobname = "/".join(job_elements)
    try:
        db.run_with_retry(parse_one, db, jobname, path, reparse,
                          mail_on_failure)
    except Exception:
        traceback.print_exc()


def parse_path(db, path, level, reparse, mail_on_failure):
    job_subdirs = _get_job_subdirs(path)
    if job_subdirs is not None:
        # parse status.log in current directory, if it exists. multi-machine
        # synchronous server side tests record output in this directory. without
        # this check, we do not parse these results.
        if os.path.exists(os.path.join(path, 'status.log')):
            parse_leaf_path(db, path, level, reparse, mail_on_failure)
        # multi-machine job
        for subdir in job_subdirs:
            jobpath = os.path.join(path, subdir)
            parse_path(db, jobpath, level + 1, reparse, mail_on_failure)
    else:
        # single machine job
        parse_leaf_path(db, path, level, reparse, mail_on_failure)


def main():
    options, args = parse_args()
    results_dir = os.path.abspath(args[0])
    assert os.path.exists(results_dir)

    pid_file_manager = pidfile.PidFileManager("parser", results_dir)

    if options.write_pidfile:
        pid_file_manager.open_file()

    try:
        # build up the list of job dirs to parse
        if options.singledir:
            jobs_list = [results_dir]
        else:
            jobs_list = [os.path.join(results_dir, subdir)
                         for subdir in os.listdir(results_dir)]

        # build up the database
        db = tko_db.db(autocommit=False, host=options.db_host,
                       user=options.db_user, password=options.db_pass,
                       database=options.db_name)

        # parse all the jobs
        for path in jobs_list:
            lockfile = open(os.path.join(path, ".parse.lock"), "w")
            flags = fcntl.LOCK_EX
            if options.noblock:
                flags |= fcntl.LOCK_NB
            try:
                fcntl.flock(lockfile, flags)
            except IOError, e:
                # lock is not available and nonblock has been requested
                if e.errno == errno.EWOULDBLOCK:
                    lockfile.close()
                    continue
                else:
                    raise # something unexpected happened
            try:
                parse_path(db, path, options.level, options.reparse,
                           options.mailit)

            finally:
                fcntl.flock(lockfile, fcntl.LOCK_UN)
                lockfile.close()

    except:
        pid_file_manager.close_file(1)
        raise
    else:
        pid_file_manager.close_file(0)


if __name__ == "__main__":
    main()
