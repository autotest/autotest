import os
import common
from autotest_lib.client.common_lib import utils


class rsync:
    command = '/usr/bin/rsync -rltvz'

    def __init__(self, prefix, target, excludes = []):
        if not os.path.isdir(target):
            os.makedirs(target)
        self.prefix = prefix
        self.target = target
        # Have to use a tmpfile rather than a pipe, else we could
        # trigger from a file that's still only partially mirrored
        self.tmpfile = '/tmp/mirror.%d' % os.getpid()
        if os.path.exists(self.tmpfile):
            os.remove(self.tmpfile)
        self.exclude = ' '.join(['--exclude ' + x for x in excludes])


    def __del__(self):
        os.remove(self.tmpfile)


    def sync(self, src, dest):
        os.chdir(self.target)
        if not os.path.isdir(dest):
            os.makedirs(dest)
        src = os.path.join(self.prefix, src)
        cmd = self.command + ' %s "%s" "%s"' % (self.exclude, src, dest)
        # print cmd + ' >> %s 2>&1' % self.tmpfile
        utils.system(cmd + ' >> %s 2>&1' % self.tmpfile)
