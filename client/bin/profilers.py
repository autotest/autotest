import os, sys
import common

from autotest_lib.client.common_lib import error, utils, packages


class ProfilerNotPresentError(error.JobError):
    pass


class profilers(object):
    def __init__(self, job):
        self.job = job
        self.list = []
        self.tmpdir = job.tmpdir
        self.profile_run_only = False
        self.active_flag = False
        self.profdir = os.path.join(job.autodir, "profilers")


    def _load_profiler(self, profiler, args, dargs):
        """ Given a name and args, loads a profiler, initializes it
        with the required arguments, and returns an instance of it. Raises
        a ProfilerNotPresentError if the module isn't found. """
        prof_dir = os.path.join(self.profdir, profiler)

        try:
            self.job.install_pkg(profiler, "profiler", prof_dir)
        except packages.PackageInstallError:
            pass

        if not os.path.exists(prof_dir):
            raise ProfilerNotPresentError("%s not present" % profiler)

        profiler_module = common.setup_modules.import_module(
            profiler, "autotest_lib.client.profilers.%s" % profiler)

        newprofiler = getattr(profiler_module, profiler)(self.job)

        newprofiler.name = profiler
        newprofiler.bindir = os.path.join(self.profdir, profiler)
        newprofiler.srcdir = os.path.join(newprofiler.bindir, 'src')
        newprofiler.tmpdir = os.path.join(self.tmpdir, profiler)
        newprofiler.initialize(*args, **dargs)
        utils.update_version(newprofiler.srcdir, newprofiler.preserve_srcdir,
                             newprofiler.version, newprofiler.setup,
                             *args, **dargs)

        return newprofiler


    def add(self, profiler, *args, **dargs):
        """ Add a profiler """
        new_profiler = self._load_profiler(profiler, args, dargs)
        self.list.append(new_profiler)


    def delete(self, profiler):
        """ Remove a profiler """
        self.list = [p for p in self.list if p.name != profiler]


    def current_profilers(self):
        """ Returns a set of the currently enabled profilers """
        return set(p.name for p in self.list)


    def present(self):
        """ Indicates if any profilers are enabled """
        return len(self.list) > 0


    def only(self):
        """ Returns True if job is supposed to be run only with profiling
        turned on, False otherwise """
        return self.profile_run_only


    def set_only(self, value):
        """ Changes the flag which determines whether or not the job is to be
        run without profilers at all """
        self.profile_run_only = value


    def start(self, test):
        """ Start all enabled profilers """
        for p in self.list:
            p.start(test)
        self.active_flag = True


    def stop(self, test):
        """ Stop all enabled profilers """
        for p in self.list:
            p.stop(test)
        self.active_flag = False


    def active(self):
        """ Returns True if profilers are present and started, False
        otherwise """
        return self.present() and self.active_flag


    def report(self, test):
        """ Report on all enabled profilers """
        for p in self.list:
            p.report(test)
