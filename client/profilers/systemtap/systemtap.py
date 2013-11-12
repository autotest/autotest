"""
Autotest systemtap profiler.
"""
import logging
import os
import re
import subprocess
from autotest.client import profiler, os_dep
from autotest.client.shared import utils, error


class systemtap(profiler.profiler):

    """
    Tracing test process using systemtap tools.
    """
    version = 1

    def initialize(self, **dargs):
        self.is_enabled = False

        stap_installed = False
        try:
            self.stap_path = os_dep.command('stap')
            stap_installed = True
        except ValueError:
            logging.error('Command stap not present')

        if stap_installed:
            self.is_enabled = True
            self.script_name = dargs.get('stap_script_file')
            stap_check_cmd = "stap -e 'probe begin { log(\"Support\") exit() }'"
            output = utils.system_output(stap_check_cmd, ignore_status=True)
            if not re.findall("Support", output):
                logging.warning("Seems your host does not support systemtap")
                self.is_enabled = False
            if not self.script_name:
                logging.warning("You should assign a script file")
                self.is_enabled = False

    def _get_stap_script_name(self, test):
        try:
            if os.path.isabs(self.script_name):
                return self.script_name
            else:
                return os.path.join(test.autodir, "profilers/systemtap/scripts", self.script_name)
        except AttributeError:
            return self.script_name

    def start(self, test):
        if self.is_enabled:
            stap_script = self._get_stap_script_name(test)
            if os.path.isfile(stap_script):
                cmd = "stap %s" % (stap_script)
                logfile = open(os.path.join(test.profdir, "systemtap.log"), 'w')
                p = subprocess.Popen(cmd, shell=True, stdout=logfile,
                                     stderr=subprocess.STDOUT)
                self.pid = p.pid
            else:
                logging.warning("Asked for systemtap profiling, but no script "
                                "file %s not found", stap_script)
                self.is_enabled = False
        else:
            logging.warning("Asked for systemtap profiling, but it couldn't "
                            "be initialized")

    def stop(self, test):
        if self.is_enabled:
            try:
                term_profiler = "kill -15 %d" % self.pid
                # send SIGTERM to iostat and give it a 5-sec timeout
                utils.system(term_profiler, timeout=5)
            except error.CmdError:  # probably times out
                pass
            # do a ps again to see if iostat is still there
            ps_cmd = "ps -p %d | grep stap" % self.pid
            out = utils.system_output(ps_cmd, ignore_status=True)
            if out != '':
                kill_profiler = 'kill -9 %d' % self.pid
                utils.system(kill_profiler, ignore_status=True)

    def report(self, test):
        return None
