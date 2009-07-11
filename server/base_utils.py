# Copyright 2008 Google Inc, Martin J. Bligh <mbligh@google.com>,
#                Benjamin Poirier, Ryan Stutsman
# Released under the GPL v2
"""
Miscellaneous small functions.

DO NOT import this file directly - it is mixed in by server/utils.py,
import that instead
"""

import atexit, os, re, shutil, textwrap, sys, tempfile, types

from autotest_lib.client.common_lib import utils
from autotest_lib.server import subcommand


# A dictionary of pid and a list of tmpdirs for that pid
__tmp_dirs = {}


def scp_remote_escape(filename):
    """
    Escape special characters from a filename so that it can be passed
    to scp (within double quotes) as a remote file.

    Bis-quoting has to be used with scp for remote files, "bis-quoting"
    as in quoting x 2
    scp does not support a newline in the filename

    Args:
            filename: the filename string to escape.

    Returns:
            The escaped filename string. The required englobing double
            quotes are NOT added and so should be added at some point by
            the caller.
    """
    escape_chars= r' !"$&' "'" r'()*,:;<=>?[\]^`{|}'

    new_name= []
    for char in filename:
        if char in escape_chars:
            new_name.append("\\%s" % (char,))
        else:
            new_name.append(char)

    return utils.sh_escape("".join(new_name))


def get(location, local_copy = False):
    """Get a file or directory to a local temporary directory.

    Args:
            location: the source of the material to get. This source may
                    be one of:
                    * a local file or directory
                    * a URL (http or ftp)
                    * a python file-like object

    Returns:
            The location of the file or directory where the requested
            content was saved. This will be contained in a temporary
            directory on the local host. If the material to get was a
            directory, the location will contain a trailing '/'
    """
    tmpdir = get_tmp_dir()

    # location is a file-like object
    if hasattr(location, "read"):
        tmpfile = os.path.join(tmpdir, "file")
        tmpfileobj = file(tmpfile, 'w')
        shutil.copyfileobj(location, tmpfileobj)
        tmpfileobj.close()
        return tmpfile

    if isinstance(location, types.StringTypes):
        # location is a URL
        if location.startswith('http') or location.startswith('ftp'):
            tmpfile = os.path.join(tmpdir, os.path.basename(location))
            utils.urlretrieve(location, tmpfile)
            return tmpfile
        # location is a local path
        elif os.path.exists(os.path.abspath(location)):
            if not local_copy:
                if os.path.isdir(location):
                    return location.rstrip('/') + '/'
                else:
                    return location
            tmpfile = os.path.join(tmpdir, os.path.basename(location))
            if os.path.isdir(location):
                tmpfile += '/'
                shutil.copytree(location, tmpfile, symlinks=True)
                return tmpfile
            shutil.copyfile(location, tmpfile)
            return tmpfile
        # location is just a string, dump it to a file
        else:
            tmpfd, tmpfile = tempfile.mkstemp(dir=tmpdir)
            tmpfileobj = os.fdopen(tmpfd, 'w')
            tmpfileobj.write(location)
            tmpfileobj.close()
            return tmpfile


def get_tmp_dir():
    """Return the pathname of a directory on the host suitable
    for temporary file storage.

    The directory and its content will be deleted automatically
    at the end of the program execution if they are still present.
    """
    dir_name = tempfile.mkdtemp(prefix="autoserv-")
    pid = os.getpid()
    if not pid in __tmp_dirs:
        __tmp_dirs[pid] = []
    __tmp_dirs[pid].append(dir_name)
    return dir_name


def __clean_tmp_dirs():
    """Erase temporary directories that were created by the get_tmp_dir()
    function and that are still present.
    """
    pid = os.getpid()
    if pid not in __tmp_dirs:
        return
    for dir in __tmp_dirs[pid]:
        try:
            shutil.rmtree(dir)
        except OSError, e:
            if e.errno == 2:
                pass
    __tmp_dirs[pid] = []
atexit.register(__clean_tmp_dirs)
subcommand.subcommand.register_join_hook(lambda _: __clean_tmp_dirs())


def unarchive(host, source_material):
    """Uncompress and untar an archive on a host.

    If the "source_material" is compresses (according to the file
    extension) it will be uncompressed. Supported compression formats
    are gzip and bzip2. Afterwards, if the source_material is a tar
    archive, it will be untarred.

    Args:
            host: the host object on which the archive is located
            source_material: the path of the archive on the host

    Returns:
            The file or directory name of the unarchived source material.
            If the material is a tar archive, it will be extracted in the
            directory where it is and the path returned will be the first
            entry in the archive, assuming it is the topmost directory.
            If the material is not an archive, nothing will be done so this
            function is "harmless" when it is "useless".
    """
    # uncompress
    if (source_material.endswith(".gz") or
            source_material.endswith(".gzip")):
        host.run('gunzip "%s"' % (utils.sh_escape(source_material)))
        source_material= ".".join(source_material.split(".")[:-1])
    elif source_material.endswith("bz2"):
        host.run('bunzip2 "%s"' % (utils.sh_escape(source_material)))
        source_material= ".".join(source_material.split(".")[:-1])

    # untar
    if source_material.endswith(".tar"):
        retval= host.run('tar -C "%s" -xvf "%s"' % (
                utils.sh_escape(os.path.dirname(source_material)),
                utils.sh_escape(source_material),))
        source_material= os.path.join(os.path.dirname(source_material),
                retval.stdout.split()[0])

    return source_material


def get_server_dir():
    path = os.path.dirname(sys.modules['autotest_lib.server.utils'].__file__)
    return os.path.abspath(path)


def find_pid(command):
    for line in utils.system_output('ps -eo pid,cmd').rstrip().split('\n'):
        (pid, cmd) = line.split(None, 1)
        if re.search(command, cmd):
            return int(pid)
    return None


def nohup(command, stdout='/dev/null', stderr='/dev/null', background=True,
                                                                env = {}):
    cmd = ' '.join(key+'='+val for key, val in env.iteritems())
    cmd += ' nohup ' + command
    cmd += ' > %s' % stdout
    if stdout == stderr:
        cmd += ' 2>&1'
    else:
        cmd += ' 2> %s' % stderr
    if background:
        cmd += ' &'
    utils.system(cmd)


def default_mappings(machines):
    """
    Returns a simple mapping in which all machines are assigned to the
    same key.  Provides the default behavior for
    form_ntuples_from_machines. """
    mappings = {}
    failures = []

    mach = machines[0]
    mappings['ident'] = [mach]
    if len(machines) > 1:
        machines = machines[1:]
        for machine in machines:
            mappings['ident'].append(machine)

    return (mappings, failures)


def form_ntuples_from_machines(machines, n=2, mapping_func=default_mappings):
    """Returns a set of ntuples from machines where the machines in an
       ntuple are in the same mapping, and a set of failures which are
       (machine name, reason) tuples."""
    ntuples = []
    (mappings, failures) = mapping_func(machines)

    # now run through the mappings and create n-tuples.
    # throw out the odd guys out
    for key in mappings:
        key_machines = mappings[key]
        total_machines = len(key_machines)

        # form n-tuples
        while len(key_machines) >= n:
            ntuples.append(key_machines[0:n])
            key_machines = key_machines[n:]

        for mach in key_machines:
            failures.append((mach, "machine can not be tupled"))

    return (ntuples, failures)


def parse_machine(machine, user = 'root', port = 22, password = ''):
    """
    Parse the machine string user:pass@host:port and return it separately,
    if the machine string is not complete, use the default parameters
    when appropriate.
    """

    user = user
    port = port
    password = password

    if re.search('@', machine):
        machine = machine.split('@')

        if re.search(':', machine[0]):
            machine[0] = machine[0].split(':')
            user = machine[0][0]
            password = machine[0][1]

        else:
            user = machine[0]

        if re.search(':', machine[1]):
            machine[1] = machine[1].split(':')
            hostname = machine[1][0]
            port = int(machine[1][1])

        else:
            hostname = machine[1]

    elif re.search(':', machine):
        machine = machine.split(':')
        hostname = machine[0]
        port = int(machine[1])

    else:
        hostname = machine

    return hostname, user, password, port


def get_public_key():
    """
    Return a valid string ssh public key for the user executing autoserv or
    autotest. If there's no DSA or RSA public key, create a DSA keypair with
    ssh-keygen and return it.
    """

    ssh_conf_path = os.path.expanduser('~/.ssh')

    dsa_public_key_path = os.path.join(ssh_conf_path, 'id_dsa.pub')
    dsa_private_key_path = os.path.join(ssh_conf_path, 'id_dsa')

    rsa_public_key_path = os.path.join(ssh_conf_path, 'id_rsa.pub')
    rsa_private_key_path = os.path.join(ssh_conf_path, 'id_rsa')

    has_dsa_keypair = os.path.isfile(dsa_public_key_path) and \
        os.path.isfile(dsa_private_key_path)
    has_rsa_keypair = os.path.isfile(rsa_public_key_path) and \
        os.path.isfile(rsa_private_key_path)

    if has_dsa_keypair:
        print 'DSA keypair found, using it'
        public_key_path = dsa_public_key_path

    elif has_rsa_keypair:
        print 'RSA keypair found, using it'
        public_key_path = rsa_public_key_path

    else:
        print 'Neither RSA nor DSA keypair found, creating DSA ssh key pair'
        utils.system('ssh-keygen -t dsa -q -N "" -f %s' % dsa_private_key_path)
        public_key_path = dsa_public_key_path

    public_key = open(public_key_path, 'r')
    public_key_str = public_key.read()
    public_key.close()

    return public_key_str
