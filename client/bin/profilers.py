import os, sys
import common

from autotest_lib.client.common_lib import utils, error, profiler_manager


class profilers(profiler_manager.profiler_manager):
    def load_profiler(self, profiler, args, dargs):
        prof_dir = os.path.join(self.job.autodir, "profilers", profiler)

        try:
            self.job.install_pkg(profiler, "profiler", prof_dir)
        except error.PackageInstallError:
            pass

        if not os.path.exists(prof_dir):
            raise profiler_manager.ProfilerNotPresentError(profiler)

        profiler_module = common.setup_modules.import_module(
            profiler, "autotest_lib.client.profilers.%s" % profiler)

        newprofiler = getattr(profiler_module, profiler)(self.job)

        newprofiler.name = profiler
        newprofiler.bindir = os.path.join(prof_dir)
        newprofiler.srcdir = os.path.join(newprofiler.bindir, 'src')
        newprofiler.tmpdir = os.path.join(self.tmpdir, profiler)
        newprofiler.initialize(*args, **dargs)
        utils.update_version(newprofiler.srcdir, newprofiler.preserve_srcdir,
                             newprofiler.version, newprofiler.setup,
                             *args, **dargs)

        return newprofiler
