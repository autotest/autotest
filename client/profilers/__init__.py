import os

try:
    import autotest.common as common  # pylint: disable=W0611
except ImportError:
    import common  # pylint: disable=W0611

from autotest.client.shared import utils, error, profiler_manager
from autotest.client.shared.settings import settings


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
            profiler, "autotest.client.profilers.%s" % profiler)

        newprofiler = getattr(profiler_module, profiler)(self.job)

        newprofiler.name = profiler
        newprofiler.bindir = os.path.join(prof_dir)
        try:
            autodir = os.path.abspath(os.environ['AUTODIR'])
        except KeyError:
            autodir = settings.get_value('COMMON', 'autotest_top_path')
        tmpdir = os.path.join(autodir, 'tmp')
        output_config = settings.get_value('COMMON', 'test_output_dir',
                                           default=tmpdir)
        newprofiler.srcdir = os.path.join(output_config,
                                          os.path.basename(newprofiler.bindir),
                                          'src')
        newprofiler.tmpdir = os.path.join(self.tmpdir, profiler)
        newprofiler.initialize(*args, **dargs)
        utils.update_version(newprofiler.srcdir, newprofiler.preserve_srcdir,
                             newprofiler.version, newprofiler.setup,
                             *args, **dargs)

        return newprofiler
