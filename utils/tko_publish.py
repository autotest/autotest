#!/usr/bin/python
"""
This script will scan an autotest server results directory for job result
directories that have completed and that have not yet been published on
a remote dashboard server matching given filtering options and for those it
finds it will rsync them to the tko server and mark them as published (it uses
a <jobdir>/.tko_published flag file to determine if a jobdir results directory
has been published yet).
"""

import sys, os, re, optparse

import common
from autotest_lib.client.common_lib import utils
from autotest_lib.server import frontend

options = optparse.Values()

USAGE="""tko-publish [options] <resultsdir> <rsync-destination-path>

Where:
<resultsdir>              A path to the directory having the job results
                          directories to publish.

<rsync-destination-path>  A valid rsync destination path where to upload the
                          job result directories.
                          Example: user@machine.org:/home/autotest/results"""
PUBLISH_FLAGFILE = '.tko_published'
RSYNC_COMMAND = 'rsync -aqz "%s" "%s"'


def get_job_dirs(path):
    regex = re.compile('[1-9][0-9]*-')
    jobdirs = []

    for dir in os.listdir(path):
        # skip directories not matching the job result dir pattern
        if not regex.match(dir):
            continue

        dir = os.path.join(options.resultsdir, dir)
        if (os.path.isdir(dir)
                and not os.path.exists(os.path.join(dir, PUBLISH_FLAGFILE))):
            jobdirs.append(dir)

    return jobdirs


def publish_job(jobdir):
    cmd = RSYNC_COMMAND % (jobdir, options.dest)
    utils.system(cmd)

    # mark the jobdir as published
    fd = open(os.path.join(jobdir, PUBLISH_FLAGFILE), 'w')
    fd.close()
    print 'Published', jobdir


def main():
    jobdirs = get_job_dirs(options.resultsdir)

    afe = frontend.AFE()
    # the way AFE API is right now is to give a whole list of jobs and can't
    # get specific jobs so minimize the queries caching the result
    finished_jobs = afe.get_jobs(finished=True)

    if options.jobname_pattern:
        jobname_pattern = re.compile(options.jobname_pattern)
    else:
        jobname_pattern = None

    # for each unpublished possible jobdir find it in the database and see
    # if it is completed
    for jobdir in jobdirs:
        job_id = int(os.path.basename(jobdir).split('-')[0])
        job = [job for job in finished_jobs if job.id == job_id]

        if len(job) != 1:
            continue

        if jobname_pattern:
            # does it match the jobname pattern?
            if not jobname_pattern.match(job[0].name):
                continue

        # does it match the wanted job owner
        if options.job_owner and options.job_owner != job[0].owner:
            continue

        publish_job(jobdir)


if __name__ == '__main__':
    parser = optparse.OptionParser(usage=USAGE)
    parser.add_option('--jobname-pattern', dest='jobname_pattern',
                      help='Regexp pattern to match against job names, by '
                      "default there won't be any matching done",
                      default=None)
    parser.add_option('--job-owner', dest='job_owner', default=None,
                      help='Job owner username to match against for the '
                      'published jobs, by default no matching is done.')
    options, args = parser.parse_args()

    if len(args) < 2:
        print USAGE
        sys.exit(-1)

    options.resultsdir = args[0]
    options.dest = args[1]
    main()
