# Copyright 2008 Google Inc, Martin J. Bligh <mbligh@google.com>,
#                Benjamin Poirier, Ryan Stutsman
# Released under the GPL v2
"""
Miscellaneous small functions.

DO NOT import this file directly - it is mixed in by server/utils.py,
import that instead
"""

import atexit
import os
import re
import shutil
import sys
import tempfile
import types

from autotest.client.shared import barrier, utils
from autotest.server import subcommand

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
    escape_chars = r' !"$&' "'" r'()*,:;<=>?[\]^`{|}'

    new_name = []
    for char in filename:
        if char in escape_chars:
            new_name.append("\\%s" % (char,))
        else:
            new_name.append(char)

    return utils.sh_escape("".join(new_name))


def get(location, local_copy=False):
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
    if pid not in __tmp_dirs:
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
        source_material = ".".join(source_material.split(".")[:-1])
    elif source_material.endswith("bz2"):
        host.run('bunzip2 "%s"' % (utils.sh_escape(source_material)))
        source_material = ".".join(source_material.split(".")[:-1])

    # untar
    if source_material.endswith(".tar"):
        retval = host.run('tar -C "%s" -xvf "%s"' % (
            utils.sh_escape(os.path.dirname(source_material)),
            utils.sh_escape(source_material),))
        source_material = os.path.join(os.path.dirname(source_material),
                                       retval.stdout.split()[0])

    return source_material


def get_server_dir():
    path = os.path.dirname(sys.modules['autotest.server.utils'].__file__)
    return os.path.abspath(path)


def find_pid(command):
    for line in utils.system_output('ps -eo pid,cmd').rstrip().split('\n'):
        (pid, cmd) = line.split(None, 1)
        if re.search(command, cmd):
            return int(pid)
    return None


def nohup(command, stdout='/dev/null', stderr='/dev/null', background=True,
          env={}):
    cmd = ' '.join(key + '=' + val for key, val in env.iteritems())
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


def parse_machine(machine, user='root', password='', port=22, profile=''):
    """
    Parse the machine string user:pass@host#profile:port and return it
    separately, if the machine string is not complete, use the default
    parameters when appropriate.
    """
    if '@' in machine:
        user, machine = machine.split('@', 1)

    if ':' in user:
        user, password = user.split(':', 1)

    if ':' in machine:
        machine, port = machine.split(':', 1)
        try:
            port = int(port)
        except ValueError:
            port, profile = port.split('#', 1)
            port = int(port)

    if '#' in machine:
        machine, profile = machine.split('#', 1)

    if not machine or not user:
        raise ValueError

    return machine, user, password, port, profile


def get_sync_control_file(control, host_name, host_num,
                          instance, num_jobs, port_base=63100):
    """
    This function is used when there is a need to run more than one
    job simultaneously starting exactly at the same time. It basically returns
    a modified control file (containing the synchronization code prepended)
    whenever it is ready to run the control file. The synchronization
    is done using barriers to make sure that the jobs start at the same time.

    Here is how the synchronization is done to make sure that the tests
    start at exactly the same time on the client.
    sc_bar is a server barrier and s_bar, c_bar are the normal barriers

                      Job1              Job2         ......      JobN
     Server:   |                        sc_bar
     Server:   |                        s_bar        ......      s_bar
     Server:   |      at.run()         at.run()      ......      at.run()
     ----------|------------------------------------------------------
     Client    |      sc_bar
     Client    |      c_bar             c_bar        ......      c_bar
     Client    |    <run test>         <run test>    ......     <run test>

    :param control: The control file which to which the above synchronization
            code will be prepended.
    :param host_name: The host name on which the job is going to run.
    :param host_num: (non negative) A number to identify the machine so that
            we have different sets of s_bar_ports for each of the machines.
    :param instance: The number of the job
    :param num_jobs: Total number of jobs that are going to run in parallel
            with this job starting at the same time.
    :param port_base: Port number that is used to derive the actual barrier
            ports.

    :return: The modified control file.
    """
    sc_bar_port = port_base
    c_bar_port = port_base
    if host_num < 0:
        print "Please provide a non negative number for the host"
        return None
    s_bar_port = port_base + 1 + host_num  # The set of s_bar_ports are
    # the same for a given machine

    sc_bar_timeout = 180
    s_bar_timeout = c_bar_timeout = 120

    # The barrier code snippet is prepended into the conrol file
    # dynamically before at.run() is called finally.
    control_new = []

    # jobid is the unique name used to identify the processes
    # trying to reach the barriers
    jobid = "%s#%d" % (host_name, instance)

    rendv = []
    # rendvstr is a temp holder for the rendezvous list of the processes
    for n in range(num_jobs):
        rendv.append("'%s#%d'" % (host_name, n))
    rendvstr = ",".join(rendv)

    if instance == 0:
        # Do the setup and wait at the server barrier
        # Clean up the tmp and the control dirs for the first instance
        control_new.append('if os.path.exists(job.tmpdir):')
        control_new.append("\t system('umount -f %s > /dev/null"
                           "2> /dev/null' % job.tmpdir,"
                           "ignore_status=True)")
        control_new.append("\t system('rm -rf ' + job.tmpdir)")
        control_new.append(
            'b0 = job.barrier("%s", "sc_bar", %d, port=%d)'
            % (jobid, sc_bar_timeout, sc_bar_port))
        control_new.append(
            'b0.rendezvous_servers("PARALLEL_MASTER", "%s")'
            % jobid)

    elif instance == 1:
        # Wait at the server barrier to wait for instance=0
        # process to complete setup
        b0 = barrier.barrier("PARALLEL_MASTER", "sc_bar", sc_bar_timeout,
                             port=sc_bar_port)
        b0.rendezvous_servers("PARALLEL_MASTER", jobid)

        if(num_jobs > 2):
            b1 = barrier.barrier(jobid, "s_bar", s_bar_timeout,
                                 port=s_bar_port)
            b1.rendezvous(rendvstr)

    else:
        # For the rest of the clients
        b2 = barrier.barrier(jobid, "s_bar", s_bar_timeout, port=s_bar_port)
        b2.rendezvous(rendvstr)

    # Client side barrier for all the tests to start at the same time
    control_new.append('b1 = job.barrier("%s", "c_bar", %d, port=%d)'
                       % (jobid, c_bar_timeout, c_bar_port))
    control_new.append("b1.rendezvous(%s)" % rendvstr)

    # Stick in the rest of the control file
    control_new.append(control)

    return "\n".join(control_new)
