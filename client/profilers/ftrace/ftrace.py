"""
Function tracer profiler for autotest.

:author: David Sharp (dhsharp@google.com)
"""
import logging
import os
import signal
import time
from autotest.client import profiler, utils
from autotest.client.shared import error


class ftrace(profiler.profiler):

    """
    ftrace profiler for autotest. It builds ftrace from souce and runs
    trace-cmd with configurable parameters.

    @see: git://git.kernel.org/pub/scm/linux/kernel/git/rostedt/trace-cmd.git
    """
    version = 1

    mountpoint = '/sys/kernel/debug'
    tracing_dir = os.path.join(mountpoint, 'tracing')

    @staticmethod
    def join_command(cmd):
        """
        Shell escape the command for BgJob. grmbl.

        :param cmd: Command list.
        """
        result = []
        for arg in cmd:
            arg = '"%s"' % utils.sh_escape(arg)
            result += [arg]
        return ' '.join(result)

    def setup(self, tarball='trace-cmd.tar.bz2', **kwargs):
        """
        Build and install trace-cmd from source.

        The tarball was obtained by checking the git repo at 09-14-2010,
        removing the Documentation and the .git folders, and compressing
        it.

        :param tarball: Path to trace-cmd tarball.
        :param **kwargs: Dictionary with additional parameters.
        """
        self.tarball = utils.unmap_url(self.bindir, tarball, self.tmpdir)
        utils.extract_tarball_to_dir(self.tarball, self.srcdir)
        os.chdir(self.srcdir)
        utils.make("prefix='%s'" % self.builddir)
        utils.make("prefix='%s' install" % self.builddir)

    def initialize(self, tracepoints, buffer_size_kb=1408, **kwargs):
        """
        Initialize ftrace profiler.

        :param tracepoints: List containing a mix of tracpoint names and
                (tracepoint name, filter) tuples. Tracepoint names are as
                accepted by trace-cmd -e, eg "syscalls", or
                "syscalls:sys_enter_read". Filters are as accepted by
                trace-cmd -f, eg "((sig >= 10 && sig < 15) || sig == 17)"
        :param buffer_size_kb: Set the size of the ring buffer (per cpu).
        """
        self.job.require_gcc()
        self.trace_cmd_args = ['-b', str(buffer_size_kb)]
        for tracepoint in tracepoints:
            if isinstance(tracepoint, tuple):
                tracepoint, event_filter = tracepoint
            else:
                event_filter = None
            self.trace_cmd_args += ['-e', tracepoint]
            if event_filter:
                self.trace_cmd_args += ['-f', event_filter]

        self.builddir = os.path.join(self.bindir, 'build')
        if not os.path.isdir(self.builddir):
            os.makedirs(self.builddir)
        self.trace_cmd = os.path.join(self.builddir, 'bin', 'trace-cmd')

    def start(self, test):
        """
        Start ftrace profiler

        :param test: Autotest test in which the profiler will operate on.
        """
        # Make sure debugfs is mounted and tracing disabled.
        utils.system('%s reset' % self.trace_cmd)

        output_dir = os.path.join(test.profdir, 'ftrace')
        if not os.path.isdir(output_dir):
            os.makedirs(output_dir)
        self.output = os.path.join(output_dir, 'trace.dat')
        cmd = [self.trace_cmd, 'record', '-o', self.output]
        cmd += self.trace_cmd_args
        self.record_job = utils.BgJob(self.join_command(cmd),
                                      stderr_tee=utils.TEE_TO_LOGS)

        # Wait for tracing to be enabled. If trace-cmd dies before enabling
        # tracing, then there was a problem.
        tracing_on = os.path.join(self.tracing_dir, 'tracing_on')
        while (self.record_job.sp.poll() is None and
               utils.read_file(tracing_on).strip() != '1'):
            time.sleep(0.1)
        if self.record_job.sp.poll() is not None:
            utils.join_bg_jobs([self.record_job])
            raise error.CmdError(self.record_job.command,
                                 self.record_job.sp.returncode,
                                 'trace-cmd exited early.')

    def stop(self, test):
        """
        Stop ftrace profiler.

        :param test: Autotest test in which the profiler will operate on.
        """
        os.kill(self.record_job.sp.pid, signal.SIGINT)
        utils.join_bg_jobs([self.record_job])
        # shrink the buffer to free memory.
        utils.system('%s reset -b 1' % self.trace_cmd)

        # compress output
        utils.system('bzip2 %s' % self.output)
        compressed_output = self.output + '.bz2'
        # if the compressed trace file is large (10MB), just delete it.
        compressed_output_size = os.path.getsize(compressed_output)
        if compressed_output_size > 10 * 1024 * 1024:
            logging.warn('Deleting large trace file %s (%d bytes)',
                         compressed_output, compressed_output_size)
            os.remove(compressed_output)
        # remove per-cpu files in case trace-cmd died.
        utils.system('rm -f %s.cpu*' % self.output)
