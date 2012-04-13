"""
Basic ISO9660 file-system support.

This code does not attempt (so far) to implement code that knows about
ISO9660 internal structure. Instead, it uses commonly available support
either in userspace tools or on the Linux kernel itself (via mount).
"""


__all__ = ['iso9660', 'Iso9660IsoInfo', 'Iso9660IsoRead', 'Iso9660Mount']


import os, logging, tempfile, shutil
import common
from autotest.client.shared import utils


def has_userland_tool(executable):
    '''
    Returns whether the system has a given executable
    '''
    if os.path.isabs(executable):
        return os.path.exists(executable)
    else:
        for d in os.environ['PATH'].split(':'):
            f = os.path.join(d, executable)
            if os.path.exists(f):
                return True
    return False


def has_isoinfo():
    '''
    Returns whether the system has the isoinfo executable

    Maybe more checks could be added to see if isoinfo supports the needed
    features
    '''
    return has_userland_tool('isoinfo')


def has_isoread():
    '''
    Returns whether the system has the isoinfo executable

    Maybe more checks could be added to see if iso-read supports the needed
    features
    '''
    return has_userland_tool('iso-read')


def can_mount():
    '''
    Test wether the current user can perform a loop mount

    AFAIK, this means being root, having mount and iso9660 kernel support
    '''
    if os.getuid() != 0:
        logging.debug('Can not use mount: current user is not "root"')
        return False

    if not has_userland_tool('mount'):
        logging.debug('Can not use mount: missing "mount" tool')
        return False

    if not 'iso9660' in open('/proc/filesystems').read():
        logging.debug('Can not use mount: lack of iso9660 kernel support')
        return False

    return True


class BaseIso9660(object):
    '''
    Represents a ISO9660 filesystem

    This class holds common functionality and has many abstract methods
    '''
    def __init__(self, path):
        self.path = path
        self._verify_path(path)


    def _verify_path(self, path):
        '''
        Verify that the current set path is accessible
        '''
        if not os.path.exists(self.path):
            raise OSError('File or device path does not exist: %s',
                          self.path)
        if not os.access(self.path, os.R_OK):
            raise OSError('File or device path could not be read: %s',
                          self.path)


    def read(self, path):
        raise NotImplementedError


    def copy(self, src, dst):
        '''
        Simplistic version of copy that relies on read()
        '''
        content = self.read(src)
        output = open(dst, 'w+b')
        output.write(content)
        output.close()


    def close(self):
        '''
        Cleanup and free any resources being used
        '''
        pass


class Iso9660IsoInfo(BaseIso9660):
    '''
    Represents a ISO9660 filesystem

    This implementation is based on the cdrkit's isoinfo tool
    '''
    def __init__(self, path):
        super(Iso9660IsoInfo, self).__init__(path)


    def _normalize_path(self, path):
        if not os.path.isabs(path):
            path = os.path.join('/', path)
        return path


    def read(self, path):
        cmd = 'isoinfo -i %s -x %s' % (self.path,
                                       self._normalize_path(path))
        result = utils.run(cmd)
        return result.stdout


class Iso9660IsoRead(BaseIso9660):
    '''
    Represents a ISO9660 filesystem

    This implementation is based on the libcdio's iso-read tool
    '''
    def __init__(self, path):
        super(Iso9660IsoRead, self).__init__(path)
        self.temp_dir = tempfile.mkdtemp()


    def read(self, path):
        temp_file = os.path.join(self.temp_dir, path)
        cmd = 'iso-read -i %s -e %s -o %s' % (self.path, path, temp_file)
        utils.run(cmd)
        return open(temp_file).read()


    def copy(self, src, dst):
        cmd = 'iso-read -i %s -e %s -o %s' % (self.path, src, dst)
        utils.run(cmd)


    def close(self):
        shutil.rmtree(self.temp_dir, True)


class Iso9660Mount(BaseIso9660):
    def __init__(self, path):
        super(Iso9660Mount, self).__init__(path)
        self.mnt_dir = tempfile.mkdtemp()
        utils.run('mount -t iso9660 -v -o loop,ro %s %s' %
                  (path, self.mnt_dir))


    def read(self, path):
        full_path = os.path.join(self.mnt_dir, path)
        return open(full_path).read()


    def copy(self, src, dst):
        full_path = os.path.join(self.mnt_dir, src)
        shutil.copy(full_path, dst)


    def close(self):
        '''
        Perform umount operation on the temporary dir
        '''
        if os.path.ismount(self.mnt_dir):
            utils.run('fuser -k %s' % self.mnt_dir, ignore_status=True)
            utils.run('umount %s' % self.mnt_dir)

        shutil.rmtree(self.mnt_dir)


def iso9660(path):
    '''
    Checks the avaiable tools on a system and chooses class accordingly

    This is a convinience function, that will pick the first avaialable
    iso9660 capable tool.

    @param path: path to an iso9660 image file
    @type path: string
    @return: an instance or None
    '''
    IMPLEMENTATIONS = [('isoinfo', has_isoinfo, Iso9660IsoInfo),
                       ('iso-read', has_isoread, Iso9660IsoRead),
                       ('mount', can_mount, Iso9660Mount)]

    for (name, check, klass) in IMPLEMENTATIONS:
        if check():
            logging.debug('Automatically chosen class for iso9660: %s', name)
            return klass(path)

    return None
