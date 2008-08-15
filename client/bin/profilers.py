import os, sys
import common
from autotest_lib.client.common_lib import error, utils, packages

class profilers:

    def __init__(self, job):
        self.job = job
        self.list = []
        self.profdir = job.autodir + '/profilers'
        self.tmpdir = job.tmpdir
        self.profile_run_only = False

    # add a profiler
    def add(self, profiler, *args, **dargs):
        prof_dir = os.path.join(self.profdir, profiler)

        try:
            self.job.install_pkg(profiler, 'prof', prof_dir)
        except packages.PackageInstallError:
            pass

        # prof_dir might not be present locally in the case where it is not
        # fetched from the repositoryr
        if not os.path.exists(prof_dir):
            raise error.JobError('profiler %s not present' % profiler)

        profiler_module = common.setup_modules.import_module(profiler,
                                  'autotest_lib.client.profilers.%s' % profiler)
        newprofiler = getattr(profiler_module, profiler)(self.job)

        newprofiler.name = profiler
        newprofiler.bindir = os.path.join(self.profdir, profiler)
        newprofiler.srcdir = os.path.join(newprofiler.bindir, 'src')
        newprofiler.tmpdir = os.path.join(self.tmpdir, profiler)
        utils.update_version(newprofiler.srcdir, newprofiler.preserve_srcdir,
                             newprofiler.version, newprofiler.setup,
                             *args, **dargs)
        newprofiler.initialize(*args, **dargs)
        self.list.append(newprofiler)


    # remove a profiler
    def delete(self, profiler):
        nukeme = None
        for p in self.list:
            if (p.name == profiler):
                nukeme = p
        self.list.remove(p)


    # are any profilers enabled ?
    def present(self):
        if self.list:
            return 1
        else:
            return 0

    # Returns True if job is supposed to be run only with profiling turned
    # on, False otherwise
    def only(self):
        return self.profile_run_only

    # Changes the flag which determines whether or not the job is to be
    # run without profilers at all
    def set_only(self, value):
        self.profile_run_only = value

    # Start all enabled profilers
    def start(self, test):
        for p in self.list:
            p.start(test)


    # Stop all enabled profilers
    def stop(self, test):
        for p in self.list:
            p.stop(test)


    # Report on all enabled profilers
    def report(self, test):
        for p in self.list:
            p.report(test)
