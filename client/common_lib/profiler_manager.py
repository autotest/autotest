import os, sys
import common

from autotest_lib.client.common_lib import error, utils, packages


class ProfilerNotPresentError(error.JobError):
    def __init__(self, name, *args, **dargs):
        msg = "%s not present" % name
        error.JobError.__init__(self, msg, *args, **dargs)


class profiler_manager(object):
    def __init__(self, job):
        self.job = job
        self.list = []
        self.tmpdir = job.tmpdir
        self.profile_run_only = False
        self.active_flag = False
        self.created_dirs = []


    def load_profiler(self, profiler, args, dargs):
        """ Given a name and args, loads a profiler, initializes it
        with the required arguments, and returns an instance of it. Raises
        a ProfilerNotPresentError if the module isn't found. """
        raise NotImplementedError("load_profiler not implemented")


    def add(self, profiler, *args, **dargs):
        """ Add a profiler """
        new_profiler = self.load_profiler(profiler, args, dargs)
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

        if getattr(test, 'iteration', None):
            name = 'iteration.%s' % test.iteration
            iter_path = os.path.join(test.profdir, name)
            os.system('mkdir -p %s' % iter_path)
            self.created_dirs.append(name)
            print self.created_dirs
            for file in os.listdir(test.profdir):
                if file in self.created_dirs:
                    continue
                file_path = os.path.join(test.profdir, file)
                iter_path_file = os.path.join(iter_path, file)
                os.rename(file_path, iter_path_file)
