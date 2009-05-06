import os, errno
from autotest_lib.client.bin import test


class profiler_test(test.test):
    version = 1


    def make_path_from_command(self, command):
        return os.path.join(self.job.autodir, "profiler.%s" % command)


    def wait_for_command(self, command):
        path = self.make_path_from_command(command)

        # create a pipe at the path
        try:
            os.mkfifo(path)
        except OSError, e:
            if e.errno == errno.EEXIST:
                os.remove(path)
                return  # already written into, no wait
            raise

        # wait for something to be written into the pipe
        fifo = open(path)
        fifo.read(1)
        fifo.close()
        os.remove(path)


    def signal_server(self, command):
        path = self.make_path_from_command(command)
        try:
            fifo = open(path, "w")
            fifo.write("A")
            fifo.close()
        except IOError, e:
            if e.errno != errno.EPIPE:
                raise   # the server may have already given up waiting


    def execute(self):
        # set up a pipe for signalling we are finished
        finished_path = self.make_path_from_command("finished")
        if os.path.exists(finished_path):
            os.remove(finished_path)
        os.mkfifo(finished_path)

        # signal the server that we're ready
        self.signal_server("ready")

        try:
            # wait until each command is signalled, and then execute the
            # equivalent job.profilers command
            self.wait_for_command("start")
            self.job.profilers.start(self)
            self.wait_for_command("stop")
            self.job.profilers.stop(self)
            self.wait_for_command("report")
            self.job.profilers.report(self)

            # signal that the profiling run is finished
            self.signal_server("finished")
        finally:
            for command in ("start", "stop", "report"):
                try:
                    os.remove(self.make_path_from_command(command))
                except OSError, e:
                    if e.errno != errno.ENOENT:
                        raise  # it may have already been removed
