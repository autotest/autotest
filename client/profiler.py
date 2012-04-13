class profiler:
    preserve_srcdir = False
    supports_reboot = False

    def __init__(self, job):
        self.job = job

    def setup(self, *args, **dargs):
        return


    def initialize(self, *args, **dargs):
        return


    def start(self, test):
        return


    def stop(self, test):
        return


    def report(self, test):
        return
