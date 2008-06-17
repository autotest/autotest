#!/usr/bin/python -u

import os, sys, optparse, fcntl, errno, traceback, socket

import common
from autotest_lib.client.common_lib import mail, utils
from autotest_lib.tko import db as tko_db, utils as tko_utils, status_lib


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
    if reparse and db.find_job(jobname):
        tko_utils.dprint("! Deleting old copy of job results to "
                         "reparse it")
        db.delete_job(jobname)
    if db.find_job(jobname):
        tko_utils.dprint("! Job is already parsed, done")
        return

    # look up the status version
    try:
        job_keyval = utils.read_keyval(path)
    except IOError, e:
        if e.errno == errno.ENOENT:
            status_version = 0
        else:
            raise
    else:
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
    job.tests = tests

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
    db.commit()


def parse_path(db, path, level, reparse, mail_on_failure):
    machine_list = os.path.join(path, ".machines")
    if os.path.exists(machine_list):
        # multi-machine job
        for m in file(machine_list):
            machine = m.rstrip()
            if not machine:
                continue
            jobpath = os.path.join(path, machine)
            jobname = "%s/%s" % (os.path.basename(path), machine)
            try:
                db.run_with_retry(parse_one, db, jobname,
                                  path, reparse,
                                  mail_on_failure)
            except Exception:
                traceback.print_exc()
                continue
    else:
        # single machine job
        job_elements = path.split("/")[-level:]
        jobname = "/".join(job_elements)
        try:
            db.run_with_retry(parse_one, db, jobname, path,
                              reparse, mail_on_failure)
        except Exception:
            traceback.print_exc()


def main():
    options, args = parse_args()
    results_dir = os.path.abspath(args[0])
    assert os.path.exists(results_dir)

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
            flags != fcntl.LOCK_NB
        try:
            fcntl.flock(lockfile, flags)
        except IOError, e:
            # was this because the lock is unavailable?
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


if __name__ == "__main__":
    main()
