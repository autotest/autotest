import os
import logging
from autotest.client.shared import error


def run_getfd(test, params, env):
    """
    Test QEMU's getfd command

    1) Boot up a guest
    2) Pass file descriptors via getfd
    3) Check if qemu process has a copy of the file descriptor

    @param test:   KVM test object.
    @param params: Dictionary with the test parameters.
    @param env:    Dictionary with test environment.
    """
    def has_fd(pid, filepath):
        """
        Returns true if process has a file descriptor pointing to filepath

        @param pid: the process id
        @param filepath: the full path for the file
        """
        pathlist = []
        dirname = "/proc/%s/fd" % pid
        dirlist = [os.path.join(dirname, f) for f in os.listdir(dirname)]
        for f in dirlist:
            if os.path.islink(f):
                pathlist.append(os.readlink(f))

        if filepath in pathlist:
            return True
        else:
            return False

    vm = env.get_vm(params["main_vm"])
    vm.verify_alive()

    pid = vm.get_pid()
    if pid is None:
        raise error.TestError("Fail to get process id for VM")

    # directory for storing temporary files
    fdfiles_dir = os.path.join(test.tmpdir, 'fdfiles')
    if not os.path.isdir(fdfiles_dir):
        os.mkdir(fdfiles_dir)

    # number of files
    nofiles = int(params.get("number_of_files", "900"))
    for n in range(nofiles):
        name = "fdfile-%s" % n
        path = os.path.join(fdfiles_dir, name)
        fd = os.open(path, os.O_RDWR | os.O_CREAT)
        response = vm.monitor.getfd(fd, name)
        os.close(fd)
        # getfd is supposed to generate no output
        if response:
            raise error.TestError("getfd returned error: %s" % response)
        # check if qemu process has a copy of the fd
        if not has_fd(pid, path):
            raise error.TestError("QEMU process does not seem to have a file "
                                   "descriptor pointing to file %s" % path)

    # clean up files
    for n in range(nofiles):
        name = "fdfile-%s" % n
        path = os.path.join(fdfiles_dir, name)
        try:
            os.unlink(path)
        except OSError:
            pass
