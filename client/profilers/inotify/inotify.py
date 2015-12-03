"""
inotify logs filesystem activity that may be directly or indirectly caused
by the test that is running. It requires the inotify-tools package, more
specifically, the inotifywait tool.

Heavily inspired / shamelessly copied from the kvm_stat profiler.

:copyright: Red Hat 2013
:author: Cleber Rosa <cleber@redhat.com>
"""
import logging
import os
import subprocess

from autotest.client import profiler, os_dep


class inotify(profiler.profiler):

    """
    Profiler based on inotifywait from inotify-tools
    """

    version = 1

    def _build_command_line(self, paths, test):
        default_opts = "-m -t 0 --format='%T|%,e|%w|%f' --timefmt '%m/%d %X'"
        paths_valid = [p for p in paths if os.path.exists(p)]
        paths_str = ' '.join(paths_valid)

        output_option = '-o %s' % os.path.join(test.profdir, 'inotify')
        options = '%s %s' % (default_opts, output_option)

        return '%s %s %s' % (self.inotifywait, options, paths_str)

    def initialize(self, paths=[]):
        try:
            self.inotifywait = os_dep.command('inotifywait')
        except ValueError:
            logging.error('Command inotifywait from inotify-tools is not present')
            self.inotifywait = None

        self.paths = paths

    def start(self, test):
        if self.inotifywait is None:
            logging.error("Profiler inotify won't perform any action because "
                          "the inotifywait tool from inotify-tools is missing "
                          "on this system")
            return

        # monitor the test directories by default
        if not self.paths:
            self.paths = [test.bindir, test.srcdir, test.tmpdir]

        self.command_line = self._build_command_line(self.paths, test)
        logging.debug('running inotify profiler command: %s',
                      self.command_line)
        p = subprocess.Popen(self.command_line,
                             shell=True,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
        self.pid = p.pid

    def stop(self, test):
        if self.inotifywait is None:
            return

        try:
            os.kill(self.pid, 15)
        except OSError:
            pass

    def report(self, test):
        return None
