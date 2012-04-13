import os


class PidFileManager(object):
    def __init__(self, label, results_dir):
        self.path = os.path.join(results_dir, ".%s_execute" % label)
        self.pid_file = None
        self.num_tests_failed = 0


    def open_file(self):
        self.pid_file = open(self.path, "w")
        self.pid_file.write("%s\n" % os.getpid())
        self.pid_file.flush()


    def close_file(self, exit_code, signal_code=0):
        if not self.pid_file:
            return
        pid_file = self.pid_file
        self.pid_file = None
        encoded_exit_code = ((exit_code & 0xFF) << 8) | (signal_code & 0xFF)
        pid_file.write("%s\n" % encoded_exit_code)
        pid_file.write("%s\n" % self.num_tests_failed)
        pid_file.close()
