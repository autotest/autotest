import os, sys, logging
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error


class selftest(test.test):
    version = 1

    def setup(self):
        name = self.job.resultdir + '/sequence'
        if (not os.path.exists(name)):
            fd = file(name, 'w')
            fd.write('0')
            fd.close()

    def __mark(self, checkpoint):
        name = self.job.resultdir + '/sequence'
        fd = file(name, 'r')
        current = int(fd.readline())
        fd.close()

        current += 1
        fd = file(name + '.new', 'w')
        fd.write('%d' % current)
        fd.close()

        os.rename(name + '.new', name)

        logging.debug("checkpoint %d %d", current, checkpoint)

        if (current != checkpoint):
            raise error.JobError("selftest: sequence was " +
                    "%d when %d expected" % (current, checkpoint))

    def __throw(self):
        __does_not_exist = __does_not_exist_either

    def __print(self, msg):
        sys.stdout.write(msg)

    def __warn(self, msg):
        sys.stderr.write(msg)

    def execute(self, cmd, *args):
        if cmd == 'mark':
            self.__mark(*args)
        elif cmd == 'throw':
            self.__throw(*args)
        elif cmd == 'print':
            self.__print(*args)
        elif cmd == 'warn':
            self.__warn(*args)
