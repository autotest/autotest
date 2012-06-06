"""
This script is used to execute a program and collect the monitor
information in background, redirect the outputs to log files.
"""

import threading, shelve, commands, re, os, sys, random, string

class Runner(object):
    def __init__(self):
        """
        Set the global paramter for thread clean up
        """
        self.kill_thread_flag = False

    def monitor_thread(self, m_cmd, p_file, r_path):
        """
        Record the parent process id and start the monitor process
        in background
        """
        fd = shelve.open(p_file)
        fd["pid"] = os.getpid()
        fd.close()
        commands.getoutput("%s &> %s_monitor" %(m_cmd, r_path))

    def thread_kill(self, cmd, p_file):
        """
        Kill the process according to its parent pid and command
        """
        fd = shelve.open(p_file)
        s, o = commands.getstatusoutput("pstree -p %s" % fd["pid"])
        try:
            tmp = cmd.split()[0]
            pid = re.findall("%s.(\d+)" % tmp, o)[0]
        except IndexError:
            return (0, "")
        s, o = commands.getstatusoutput("kill -9 %s" % pid)
        fd.close()
        return (s, o)

    def test_thread(self, m_cmd, t_cmd, p_file):
        """
        Test thread
        """
        self.kill_thread_flag = True
        s, o = commands.getstatusoutput(t_cmd)
        if s != 0:
            print "Test failed or timeout: %s" % o
        if self.kill_thread_flag:
            s, o = self.thread_kill(m_cmd, p_file)
            if s != 0:
                print "Monitor process is still alive, %s" % o
            else:
                self.kill_thread_flag = False

    def run(self, m_cmd, t_cmd, r_path, timeout):
        """
        Main thread for testing, will do clean up afterwards
        """
        pid_file = "/tmp/pid_file_%s" % "".join(random.sample(string.letters,
                                                 4))
        monitor = threading.Thread(target=self.monitor_thread,args=(m_cmd,
                                   pid_file, r_path))
        test_runner = threading.Thread(target=self.test_thread, args=(m_cmd,
                                       t_cmd, pid_file))

        monitor.start()
        test_runner.start()
        monitor.join(timeout)
        if self.kill_thread_flag:
            s, o = self.thread_kill(m_cmd, pid_file)
            s, o = self.thread_kill(t_cmd, pid_file)
            self.kill_thread_flag = False


if __name__ == '__main__':
    if len(sys.argv) < 4:
        this = os.path.basename(sys.argv[0])
        print "Usage: %s <monitor_cmd> <test_cmd> <test_path> <timeout>" % this
        sys.exit(1)

    monitor_cmd = sys.argv[1]
    test_cmd = sys.argv[2]
    test_path = sys.argv[3]
    test_cmd = test_cmd % test_path
    timeout = int(sys.argv[4])
    r = Runner()
    r.run(monitor_cmd, test_cmd, test_path, timeout)

