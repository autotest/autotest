import os, time, pickle, logging

from autotest_lib.server import utils, profiler


# import any site hooks for the crashdump and crashinfo collection
get_site_crashdumps = utils.import_site_function(
    __file__, "autotest_lib.server.site_crashcollect", "get_site_crashdumps",
    lambda host, test_start_time: None)
get_site_crashinfo = utils.import_site_function(
    __file__, "autotest_lib.server.site_crashcollect", "get_site_crashinfo",
    lambda host, test_start_time: None)


def get_crashdumps(host, test_start_time):
    get_site_crashdumps(host, test_start_time)


def get_crashinfo(host, test_start_time):
    logging.info("Collecting crash information...")

    # include crashdumps as part of the general crashinfo
    get_crashdumps(host, test_start_time)

    # wait for four hours, to see if the machine comes back up
    current_time = time.strftime("%b %d %H:%M:%S", time.localtime())
    logging.info("Waiting four hours for %s to come up (%s)",
                 host.hostname, current_time)
    if not host.wait_up(timeout=4*60*60):
        logging.warning("%s down, unable to collect crash info",
                        host.hostname)
        return
    else:
        logging.info("%s is back up, collecting crash info", host.hostname)

    # run any site-specific crashinfo collection
    get_site_crashinfo(host, test_start_time)

    # find a directory to put the crashinfo into
    host_resultdir = getattr(getattr(host, "job", None), "resultdir", None)
    if host_resultdir:
        infodir = host_resultdir
    else:
        infodir = os.path.abspath(os.getcwd())
    infodir = os.path.join(infodir, "crashinfo.%s" % host.hostname)
    if not os.path.exists(infodir):
        os.mkdir(infodir)

    # collect various log files
    log_files = ["/var/log/messages", "/var/log/monitor-ssh-reboots"]
    for log in log_files:
        logging.info("Collecting %s...", log)
        try:
            host.get_file(log, infodir, preserve_perm=False)
        except Exception:
            logging.warning("Collection of %s failed", log)

    # collect dmesg
    logging.info("Collecting dmesg (saved to crashinfo/dmesg)...")
    devnull = open("/dev/null", "w")
    try:
        try:
            result = host.run("dmesg", stdout_tee=devnull).stdout
            file(os.path.join(infodir, "dmesg"), "w").write(result)
        except Exception, e:
            logging.warning("Collection of dmesg failed:\n%s", e)
    finally:
        devnull.close()

    # collect any profiler data we can find
    logging.info("Collecting any server-side profiler data lying around...")
    try:
        cmd = "ls %s" % profiler.PROFILER_TMPDIR
        profiler_dirs = [path for path in host.run(cmd).stdout.split()
                         if path.startswith("autoserv-")]
        for profiler_dir in profiler_dirs:
            remote_path = profiler.get_profiler_results_dir(profiler_dir)
            remote_exists = host.run("ls %s" % remote_path,
                                     ignore_status=True).exit_status == 0
            if not remote_exists:
                continue
            local_path = os.path.join(infodir, "profiler." + profiler_dir)
            os.mkdir(local_path)
            host.get_file(remote_path + "/", local_path)
    except Exception, e:
        logging.warning("Collection of profiler data failed with:\n%s", e)


    # collect any uncollected logs we see (for this host)
    if not host.job.uncollected_log_file:
        host.job.uncollected_log_file = ''
    if host.job and os.path.exists(host.job.uncollected_log_file):
        try:
            logs = pickle.load(open(host.job.uncollected_log_file))
            for hostname, remote_path, local_path in logs:
                if hostname == host.hostname:
                    logging.info("Retrieving logs from %s:%s into %s",
                                hostname, remote_path, local_path)
                    host.get_file(remote_path + "/", local_path + "/")
        except Exception, e:
            logging.warning("Error while trying to collect stranded "
                           "Autotest client logs: %s", e)
