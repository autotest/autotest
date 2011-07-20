#!/usr/bin/python

import fcntl, os, signal, subprocess, StringIO
import tempfile, textwrap, time, unittest
import monitors_util


def InlineStringIO(text):
    return StringIO.StringIO(textwrap.dedent(text).strip())


class WriteLoglineTestCase(unittest.TestCase):
    def setUp(self):
        self.time_tuple = (2008, 10, 31, 18, 58, 17, 4, 305, 1)
        self.format = '[%Y-%m-%d %H:%M:%S]'
        self.formatted_time_tuple = '[2008-10-31 18:58:17]'
        self.msg = 'testing testing'

        # Stub out time.localtime()
        self.orig_localtime = time.localtime
        time.localtime = lambda: self.time_tuple


    def tearDown(self):
        time.localtime = self.orig_localtime


    def test_prepend_timestamp(self):
        timestamped = monitors_util.prepend_timestamp(
            self.msg, self.format)
        self.assertEquals(
            '%s\t%s' % (self.formatted_time_tuple, self.msg), timestamped)


    def test_write_logline_with_timestamp(self):
        logfile = StringIO.StringIO()
        monitors_util.write_logline(logfile, self.msg, self.format)
        logfile.seek(0)
        written = logfile.read()
        self.assertEquals(
            '%s\t%s\n' % (self.formatted_time_tuple, self.msg), written)


    def test_write_logline_without_timestamp(self):
        logfile = StringIO.StringIO()
        monitors_util.write_logline(logfile, self.msg)
        logfile.seek(0)
        written = logfile.read()
        self.assertEquals(
            '%s\n' % self.msg, written)


class AlertHooksTestCase(unittest.TestCase):
    def setUp(self):
        self.msg_template = 'alert yay %s haha %s'
        self.params = ('foo', 'bar')
        self.epoch_seconds = 1225501829.9300611
        # Stub out time.time
        self.orig_time = time.time
        time.time = lambda: self.epoch_seconds


    def tearDown(self):
        time.time = self.orig_time


    def test_make_alert(self):
        warnfile = StringIO.StringIO()
        alert = monitors_util.make_alert(warnfile, "MSGTYPE",
                                         self.msg_template)
        alert(*self.params)
        warnfile.seek(0)
        written = warnfile.read()
        ts = str(int(self.epoch_seconds))
        expected = '%s\tMSGTYPE\t%s\n' % (ts, self.msg_template % self.params)
        self.assertEquals(expected, written)


    def test_build_alert_hooks(self):
        warnfile = StringIO.StringIO()
        patterns_file = InlineStringIO("""
            BUG
            ^.*Kernel panic ?(.*)
            machine panic'd (%s)

            BUG
            ^.*Oops ?(.*)
            machine Oops'd (%s)
            """)
        hooks = monitors_util.build_alert_hooks(patterns_file, warnfile)
        self.assertEquals(len(hooks), 2)


class ProcessInputTestCase(unittest.TestCase):
    def test_process_input_simple(self):
        input = InlineStringIO("""
            woo yay
            this is a line
            booya
            """)
        logfile = StringIO.StringIO()
        monitors_util.process_input(input, logfile)
        input.seek(0)
        logfile.seek(0)

        self.assertEquals(
            '%s\n%s\n' % (input.read(), monitors_util.TERM_MSG),
            logfile.read())


class FollowFilesTestCase(unittest.TestCase):
    def setUp(self):
        self.logfile_dirpath = tempfile.mkdtemp()
        self.logfile_path = os.path.join(self.logfile_dirpath, 'messages')
        self.firstline = 'bip\n'
        self.lastline_seen = 'wooo\n'
        self.line_after_lastline_seen = 'yeah\n'
        self.lastline = 'pow\n'

        self.logfile = open(self.logfile_path, 'w')
        self.logfile.write(self.firstline)
        self.logfile.write(self.lastline_seen)
        self.logfile.write(self.line_after_lastline_seen)  # 3
        self.logfile.write('man\n')   # 2
        self.logfile.write(self.lastline)   # 1
        self.logfile.close()

        self.lastlines_dirpath = tempfile.mkdtemp()
        monitors_util.write_lastlines_file(
            self.lastlines_dirpath, self.logfile_path, self.lastline_seen)


    def test_lookup_lastlines(self):
        reverse_lineno = monitors_util.lookup_lastlines(
            self.lastlines_dirpath, self.logfile_path)
        self.assertEquals(reverse_lineno, 3)


    def test_nonblocking(self):
        po = subprocess.Popen('echo', stdout=subprocess.PIPE)
        flags = fcntl.fcntl(po.stdout, fcntl.F_GETFL)
        self.assertEquals(flags, 0)
        monitors_util.nonblocking(po.stdout)
        flags = fcntl.fcntl(po.stdout, fcntl.F_GETFL)
        self.assertEquals(flags, 2048)
        po.wait()


    def test_follow_files_nostate(self):
        follow_paths = [self.logfile_path]
        lastlines_dirpath = tempfile.mkdtemp()
        procs, pipes = monitors_util.launch_tails(
            follow_paths, lastlines_dirpath)
        lines, bad_pipes = monitors_util.poll_tail_pipes(
            pipes, lastlines_dirpath)
        first_shouldmatch = '[%s]\t%s' % (
            self.logfile_path, self.lastline)
        self.assertEquals(lines[0], first_shouldmatch)
        monitors_util.snuff(procs.values())


    def test_follow_files(self):
        follow_paths = [self.logfile_path]
        procs, pipes = monitors_util.launch_tails(
            follow_paths, self.lastlines_dirpath)
        lines, bad_pipes = monitors_util.poll_tail_pipes(
            pipes, self.lastlines_dirpath)
        first_shouldmatch = '[%s]\t%s' % (
            self.logfile_path, self.line_after_lastline_seen)
        self.assertEquals(lines[0], first_shouldmatch)
        monitors_util.snuff(procs.values())
        last_shouldmatch = '[%s]\t%s' % (self.logfile_path, self.lastline)
        self.assertEquals(lines[-1], last_shouldmatch)


if __name__ == '__main__':
    unittest.main()
