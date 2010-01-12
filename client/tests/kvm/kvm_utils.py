"""
KVM test utility functions.

@copyright: 2008-2009 Red Hat Inc.
"""

import md5, sha, thread, subprocess, time, string, random, socket, os, signal
import select, re, logging, commands, cPickle, pty
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
import kvm_subprocess


def dump_env(obj, filename):
    """
    Dump KVM test environment to a file.

    @param filename: Path to a file where the environment will be dumped to.
    """
    file = open(filename, "w")
    cPickle.dump(obj, file)
    file.close()


def load_env(filename, default=None):
    """
    Load KVM test environment from an environment file.

    @param filename: Path to a file where the environment was dumped to.
    """
    try:
        file = open(filename, "r")
    except:
        return default
    obj = cPickle.load(file)
    file.close()
    return obj


def get_sub_dict(dict, name):
    """
    Return a "sub-dict" corresponding to a specific object.

    Operate on a copy of dict: for each key that ends with the suffix
    "_" + name, strip the suffix from the key, and set the value of
    the stripped key to that of the key. Return the resulting dict.

    @param name: Suffix of the key we want to set the value.
    """
    suffix = "_" + name
    new_dict = dict.copy()
    for key in dict.keys():
        if key.endswith(suffix):
            new_key = key.split(suffix)[0]
            new_dict[new_key] = dict[key]
    return new_dict


def get_sub_dict_names(dict, keyword):
    """
    Return a list of "sub-dict" names that may be extracted with get_sub_dict.

    This function may be modified to change the behavior of all functions that
    deal with multiple objects defined in dicts (e.g. VMs, images, NICs).

    @param keyword: A key in dict (e.g. "vms", "images", "nics").
    """
    names = dict.get(keyword)
    if names:
        return names.split()
    else:
        return []


# Functions related to MAC/IP addresses

def mac_str_to_int(addr):
    """
    Convert MAC address string to integer.

    @param addr: String representing the MAC address.
    """
    return sum(int(s, 16) * 256 ** i
               for i, s in enumerate(reversed(addr.split(":"))))


def mac_int_to_str(addr):
    """
    Convert MAC address integer to string.

    @param addr: Integer representing the MAC address.
    """
    return ":".join("%02x" % (addr >> 8 * i & 0xFF)
                    for i in reversed(range(6)))


def ip_str_to_int(addr):
    """
    Convert IP address string to integer.

    @param addr: String representing the IP address.
    """
    return sum(int(s) * 256 ** i
               for i, s in enumerate(reversed(addr.split("."))))


def ip_int_to_str(addr):
    """
    Convert IP address integer to string.

    @param addr: Integer representing the IP address.
    """
    return ".".join(str(addr >> 8 * i & 0xFF)
                    for i in reversed(range(4)))


def offset_mac(base, offset):
    """
    Add offset to a given MAC address.

    @param base: String representing a MAC address.
    @param offset: Offset to add to base (integer)
    @return: A string representing the offset MAC address.
    """
    return mac_int_to_str(mac_str_to_int(base) + offset)


def offset_ip(base, offset):
    """
    Add offset to a given IP address.

    @param base: String representing an IP address.
    @param offset: Offset to add to base (integer)
    @return: A string representing the offset IP address.
    """
    return ip_int_to_str(ip_str_to_int(base) + offset)


def get_mac_ip_pair_from_dict(dict):
    """
    Fetch a MAC-IP address pair from dict and return it.

    The parameters in dict are expected to conform to a certain syntax.
    Typical usage may be:

    address_ranges = r1 r2 r3

    address_range_base_mac_r1 = 55:44:33:22:11:00
    address_range_base_ip_r1 = 10.0.0.0
    address_range_size_r1 = 16

    address_range_base_mac_r2 = 55:44:33:22:11:40
    address_range_base_ip_r2 = 10.0.0.60
    address_range_size_r2 = 25

    address_range_base_mac_r3 = 55:44:33:22:12:10
    address_range_base_ip_r3 = 10.0.1.20
    address_range_size_r3 = 230

    address_index = 0

    All parameters except address_index specify a MAC-IP address pool.  The
    pool consists of several MAC-IP address ranges.
    address_index specified the index of the desired MAC-IP pair from the pool.

    @param dict: The dictionary from which to fetch the addresses.
    """
    index = int(dict.get("address_index", 0))
    for mac_range_name in get_sub_dict_names(dict, "address_ranges"):
        mac_range_params = get_sub_dict(dict, mac_range_name)
        mac_base = mac_range_params.get("address_range_base_mac")
        ip_base = mac_range_params.get("address_range_base_ip")
        size = int(mac_range_params.get("address_range_size", 1))
        if index < size:
            return (mac_base and offset_mac(mac_base, index),
                    ip_base and offset_ip(ip_base, index))
        index -= size
    return (None, None)


def verify_ip_address_ownership(ip, macs, timeout=10.0):
    """
    Use arping and the ARP cache to make sure a given IP address belongs to one
    of the given MAC addresses.

    @param ip: An IP address.
    @param macs: A list or tuple of MAC addresses.
    @return: True iff ip is assigned to a MAC address in macs.
    """
    # Compile a regex that matches the given IP address and any of the given
    # MAC addresses
    mac_regex = "|".join("(%s)" % mac for mac in macs)
    regex = re.compile(r"\b%s\b.*\b(%s)\b" % (ip, mac_regex), re.IGNORECASE)

    # Check the ARP cache
    o = commands.getoutput("/sbin/arp -n")
    if regex.search(o):
        return True

    # Get the name of the bridge device for arping
    o = commands.getoutput("/sbin/ip route get %s" % ip)
    dev = re.findall("dev\s+\S+", o, re.IGNORECASE)
    if not dev:
        return False
    dev = dev[0].split()[-1]

    # Send an ARP request
    o = commands.getoutput("/sbin/arping -f -c 3 -I %s %s" % (dev, ip))
    return bool(regex.search(o))


# Functions for working with the environment (a dict-like object)

def is_vm(obj):
    """
    Tests whether a given object is a VM object.

    @param obj: Python object (pretty much everything on python).
    """
    return obj.__class__.__name__ == "VM"


def env_get_all_vms(env):
    """
    Return a list of all VM objects on a given environment.

    @param env: Dictionary with environment items.
    """
    vms = []
    for obj in env.values():
        if is_vm(obj):
            vms.append(obj)
    return vms


def env_get_vm(env, name):
    """
    Return a VM object by its name.

    @param name: VM name.
    """
    return env.get("vm__%s" % name)


def env_register_vm(env, name, vm):
    """
    Register a given VM in a given env.

    @param env: Environment where we will register the VM.
    @param name: VM name.
    @param vm: VM object.
    """
    env["vm__%s" % name] = vm


def env_unregister_vm(env, name):
    """
    Remove a given VM from a given env.

    @param env: Environment where we will un-register the VM.
    @param name: VM name.
    """
    del env["vm__%s" % name]


# Utility functions for dealing with external processes

def pid_exists(pid):
    """
    Return True if a given PID exists.

    @param pid: Process ID number.
    """
    try:
        os.kill(pid, 0)
        return True
    except:
        return False


def safe_kill(pid, signal):
    """
    Attempt to send a signal to a given process that may or may not exist.

    @param signal: Signal number.
    """
    try:
        os.kill(pid, signal)
        return True
    except:
        return False


def kill_process_tree(pid, sig=signal.SIGKILL):
    """Signal a process and all of its children.

    If the process does not exist -- return.

    @param pid: The pid of the process to signal.
    @param sig: The signal to send to the processes.
    """
    if not safe_kill(pid, signal.SIGSTOP):
        return
    children = commands.getoutput("ps --ppid=%d -o pid=" % pid).split()
    for child in children:
        kill_process_tree(int(child), sig)
    safe_kill(pid, sig)
    safe_kill(pid, signal.SIGCONT)


def get_latest_kvm_release_tag(release_listing):
    """
    Fetches the latest release tag for KVM.

    @param release_listing: URL that contains a list of the Source Forge
            KVM project files.
    """
    try:
        release_page = utils.urlopen(release_listing)
        data = release_page.read()
        release_page.close()
        rx = re.compile("kvm-(\d+).tar.gz", re.IGNORECASE)
        matches = rx.findall(data)
        # In all regexp matches to something that looks like a release tag,
        # get the largest integer. That will be our latest release tag.
        latest_tag = max(int(x) for x in matches)
        return str(latest_tag)
    except Exception, e:
        message = "Could not fetch latest KVM release tag: %s" % str(e)
        logging.error(message)
        raise error.TestError(message)


def get_git_branch(repository, branch, srcdir, commit=None, lbranch=None):
    """
    Retrieves a given git code repository.

    @param repository: Git repository URL
    """
    logging.info("Fetching git [REP '%s' BRANCH '%s' TAG '%s'] -> %s",
                 repository, branch, commit, srcdir)
    if not os.path.exists(srcdir):
        os.makedirs(srcdir)
    os.chdir(srcdir)

    if os.path.exists(".git"):
        utils.system("git reset --hard")
    else:
        utils.system("git init")

    if not lbranch:
        lbranch = branch

    utils.system("git fetch -q -f -u -t %s %s:%s" %
                 (repository, branch, lbranch))
    utils.system("git checkout %s" % lbranch)
    if commit:
        utils.system("git checkout %s" % commit)

    h = utils.system_output('git log --pretty=format:"%H" -1')
    desc = utils.system_output("git describe")
    logging.info("Commit hash for %s is %s (%s)" % (repository, h.strip(),
                                                    desc))
    return srcdir


def unload_module(module_name):
    """
    Removes a module. Handles dependencies. If even then it's not possible
    to remove one of the modules, it will trhow an error.CmdError exception.

    @param module_name: Name of the module we want to remove.
    """
    l_raw = utils.system_output("/sbin/lsmod").splitlines()
    lsmod = [x for x in l_raw if x.split()[0] == module_name]
    if len(lsmod) > 0:
        line_parts = lsmod[0].split()
        if len(line_parts) == 4:
            submodules = line_parts[3].split(",")
            for submodule in submodules:
                unload_module(submodule)
        utils.system("/sbin/modprobe -r %s" % module_name)
        logging.info("Module %s unloaded" % module_name)
    else:
        logging.info("Module %s is already unloaded" % module_name)


def check_kvm_source_dir(source_dir):
    """
    Inspects the kvm source directory and verifies its disposition. In some
    occasions build may be dependant on the source directory disposition.
    The reason why the return codes are numbers is that we might have more
    changes on the source directory layout, so it's not scalable to just use
    strings like 'old_repo', 'new_repo' and such.

    @param source_dir: Source code path that will be inspected.
    """
    os.chdir(source_dir)
    has_qemu_dir = os.path.isdir('qemu')
    has_kvm_dir = os.path.isdir('kvm')
    if has_qemu_dir and not has_kvm_dir:
        logging.debug("qemu directory detected, source dir layout 1")
        return 1
    if has_kvm_dir and not has_qemu_dir:
        logging.debug("kvm directory detected, source dir layout 2")
        return 2
    else:
        raise error.TestError("Unknown source dir layout, cannot proceed.")


# The following are functions used for SSH, SCP and Telnet communication with
# guests.

def remote_login(command, password, prompt, linesep="\n", timeout=10):
    """
    Log into a remote host (guest) using SSH or Telnet. Run the given command
    using kvm_spawn and provide answers to the questions asked. If timeout
    expires while waiting for output from the child (e.g. a password prompt
    or a shell prompt) -- fail.

    @brief: Log into a remote host (guest) using SSH or Telnet.

    @param command: The command to execute (e.g. "ssh root@localhost")
    @param password: The password to send in reply to a password prompt
    @param prompt: The shell prompt that indicates a successful login
    @param linesep: The line separator to send instead of "\\n"
            (sometimes "\\r\\n" is required)
    @param timeout: The maximal time duration (in seconds) to wait for each
            step of the login procedure (i.e. the "Are you sure" prompt, the
            password prompt, the shell prompt, etc)

    @return Return the kvm_spawn object on success and None on failure.
    """
    sub = kvm_subprocess.kvm_shell_session(command,
                                           linesep=linesep,
                                           prompt=prompt)

    password_prompt_count = 0

    logging.debug("Trying to login with command '%s'" % command)

    while True:
        (match, text) = sub.read_until_last_line_matches(
                [r"[Aa]re you sure", r"[Pp]assword:\s*$", r"^\s*[Ll]ogin:\s*$",
                 r"[Cc]onnection.*closed", r"[Cc]onnection.*refused", prompt],
                 timeout=timeout, internal_timeout=0.5)
        if match == 0:  # "Are you sure you want to continue connecting"
            logging.debug("Got 'Are you sure...'; sending 'yes'")
            sub.sendline("yes")
            continue
        elif match == 1:  # "password:"
            if password_prompt_count == 0:
                logging.debug("Got password prompt; sending '%s'" % password)
                sub.sendline(password)
                password_prompt_count += 1
                continue
            else:
                logging.debug("Got password prompt again")
                sub.close()
                return None
        elif match == 2:  # "login:"
            logging.debug("Got unexpected login prompt")
            sub.close()
            return None
        elif match == 3:  # "Connection closed"
            logging.debug("Got 'Connection closed'")
            sub.close()
            return None
        elif match == 4:  # "Connection refused"
            logging.debug("Got 'Connection refused'")
            sub.close()
            return None
        elif match == 5:  # prompt
            logging.debug("Got shell prompt -- logged in")
            return sub
        else:  # match == None
            logging.debug("Timeout elapsed or process terminated")
            sub.close()
            return None


def remote_scp(command, password, timeout=300, login_timeout=10):
    """
    Run the given command using kvm_spawn and provide answers to the questions
    asked. If timeout expires while waiting for the transfer to complete ,
    fail. If login_timeout expires while waiting for output from the child
    (e.g. a password prompt), fail.

    @brief: Transfer files using SCP, given a command line.

    @param command: The command to execute
        (e.g. "scp -r foobar root@localhost:/tmp/").
    @param password: The password to send in reply to a password prompt.
    @param timeout: The time duration (in seconds) to wait for the transfer
        to complete.
    @param login_timeout: The maximal time duration (in seconds) to wait for
        each step of the login procedure (i.e. the "Are you sure" prompt or the
        password prompt)

    @return: True if the transfer succeeds and False on failure.
    """
    sub = kvm_subprocess.kvm_expect(command)

    password_prompt_count = 0
    _timeout = login_timeout

    logging.debug("Trying to login...")

    while True:
        (match, text) = sub.read_until_last_line_matches(
                [r"[Aa]re you sure", r"[Pp]assword:\s*$", r"lost connection"],
                timeout=_timeout, internal_timeout=0.5)
        if match == 0:  # "Are you sure you want to continue connecting"
            logging.debug("Got 'Are you sure...'; sending 'yes'")
            sub.sendline("yes")
            continue
        elif match == 1:  # "password:"
            if password_prompt_count == 0:
                logging.debug("Got password prompt; sending '%s'" % password)
                sub.sendline(password)
                password_prompt_count += 1
                _timeout = timeout
                continue
            else:
                logging.debug("Got password prompt again")
                sub.close()
                return False
        elif match == 2:  # "lost connection"
            logging.debug("Got 'lost connection'")
            sub.close()
            return False
        else:  # match == None
            logging.debug("Timeout elapsed or process terminated")
            status = sub.get_status()
            sub.close()
            return status == 0


def scp_to_remote(host, port, username, password, local_path, remote_path,
                  timeout=300):
    """
    Copy files to a remote host (guest).

    @param host: Hostname or IP address
    @param username: Username (if required)
    @param password: Password (if required)
    @param local_path: Path on the local machine where we are copying from
    @param remote_path: Path on the remote machine where we are copying to
    @param timeout: Time in seconds that we will wait before giving up to
            copy the files.

    @return: True on success and False on failure.
    """
    command = ("scp -o UserKnownHostsFile=/dev/null "
               "-o PreferredAuthentications=password -r -P %s %s %s@%s:%s" %
               (port, local_path, username, host, remote_path))
    return remote_scp(command, password, timeout)


def scp_from_remote(host, port, username, password, remote_path, local_path,
                    timeout=300):
    """
    Copy files from a remote host (guest).

    @param host: Hostname or IP address
    @param username: Username (if required)
    @param password: Password (if required)
    @param local_path: Path on the local machine where we are copying from
    @param remote_path: Path on the remote machine where we are copying to
    @param timeout: Time in seconds that we will wait before giving up to copy
            the files.

    @return: True on success and False on failure.
    """
    command = ("scp -o UserKnownHostsFile=/dev/null "
               "-o PreferredAuthentications=password -r -P %s %s@%s:%s %s" %
               (port, username, host, remote_path, local_path))
    return remote_scp(command, password, timeout)


def ssh(host, port, username, password, prompt, linesep="\n", timeout=10):
    """
    Log into a remote host (guest) using SSH.

    @param host: Hostname or IP address
    @param username: Username (if required)
    @param password: Password (if required)
    @param prompt: Shell prompt (regular expression)
    @timeout: Time in seconds that we will wait before giving up on logging
            into the host.

    @return: kvm_spawn object on success and None on failure.
    """
    command = ("ssh -o UserKnownHostsFile=/dev/null "
               "-o PreferredAuthentications=password -p %s %s@%s" %
               (port, username, host))
    return remote_login(command, password, prompt, linesep, timeout)


def telnet(host, port, username, password, prompt, linesep="\n", timeout=10):
    """
    Log into a remote host (guest) using Telnet.

    @param host: Hostname or IP address
    @param username: Username (if required)
    @param password: Password (if required)
    @param prompt: Shell prompt (regular expression)
    @timeout: Time in seconds that we will wait before giving up on logging
            into the host.

    @return: kvm_spawn object on success and None on failure.
    """
    command = "telnet -l %s %s %s" % (username, host, port)
    return remote_login(command, password, prompt, linesep, timeout)


def netcat(host, port, username, password, prompt, linesep="\n", timeout=10):
    """
    Log into a remote host (guest) using Netcat.

    @param host: Hostname or IP address
    @param username: Username (if required)
    @param password: Password (if required)
    @param prompt: Shell prompt (regular expression)
    @timeout: Time in seconds that we will wait before giving up on logging
            into the host.

    @return: kvm_spawn object on success and None on failure.
    """
    command = "nc %s %s" % (host, port)
    return remote_login(command, password, prompt, linesep, timeout)


# The following are utility functions related to ports.

def is_port_free(port):
    """
    Return True if the given port is available for use.

    @param port: Port number
    """
    try:
        s = socket.socket()
        #s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("localhost", port))
        free = True
    except socket.error:
        free = False
    s.close()
    return free


def find_free_port(start_port, end_port):
    """
    Return a free port in the range [start_port, end_port).

    @param start_port: First port that will be checked.
    @param end_port: Port immediately after the last one that will be checked.
    """
    for i in range(start_port, end_port):
        if is_port_free(i):
            return i
    return None


def find_free_ports(start_port, end_port, count):
    """
    Return count free ports in the range [start_port, end_port).

    @count: Initial number of ports known to be free in the range.
    @param start_port: First port that will be checked.
    @param end_port: Port immediately after the last one that will be checked.
    """
    ports = []
    i = start_port
    while i < end_port and count > 0:
        if is_port_free(i):
            ports.append(i)
            count -= 1
        i += 1
    return ports


# The following are miscellaneous utility functions.

def get_path(base_path, user_path):
    """
    Translate a user specified path to a real path.
    If user_path is relative, append it to base_path.
    If user_path is absolute, return it as is.

    @param base_path: The base path of relative user specified paths.
    @param user_path: The user specified path.
    """
    if os.path.isabs(user_path):
        return user_path
    else:
        return os.path.join(base_path, user_path)


def generate_random_string(length):
    """
    Return a random string using alphanumeric characters.

    @length: length of the string that will be generated.
    """
    r = random.SystemRandom()
    str = ""
    chars = string.letters + string.digits
    while length > 0:
        str += r.choice(chars)
        length -= 1
    return str


def format_str_for_message(str):
    """
    Format str so that it can be appended to a message.
    If str consists of one line, prefix it with a space.
    If str consists of multiple lines, prefix it with a newline.

    @param str: string that will be formatted.
    """
    lines = str.splitlines()
    num_lines = len(lines)
    str = "\n".join(lines)
    if num_lines == 0:
        return ""
    elif num_lines == 1:
        return " " + str
    else:
        return "\n" + str


def wait_for(func, timeout, first=0.0, step=1.0, text=None):
    """
    If func() evaluates to True before timeout expires, return the
    value of func(). Otherwise return None.

    @brief: Wait until func() evaluates to True.

    @param timeout: Timeout in seconds
    @param first: Time to sleep before first attempt
    @param steps: Time to sleep between attempts in seconds
    @param text: Text to print while waiting, for debug purposes
    """
    start_time = time.time()
    end_time = time.time() + timeout

    time.sleep(first)

    while time.time() < end_time:
        if text:
            logging.debug("%s (%f secs)" % (text, time.time() - start_time))

        output = func()
        if output:
            return output

        time.sleep(step)

    logging.debug("Timeout elapsed")
    return None


def hash_file(filename, size=None, method="md5"):
    """
    Calculate the hash of filename.
    If size is not None, limit to first size bytes.
    Throw exception if something is wrong with filename.
    Can be also implemented with bash one-liner (assuming size%1024==0):
    dd if=filename bs=1024 count=size/1024 | sha1sum -

    @param filename: Path of the file that will have its hash calculated.
    @param method: Method used to calculate the hash. Supported methods:
            * md5
            * sha1
    @returns: Hash of the file, if something goes wrong, return None.
    """
    chunksize = 4096
    fsize = os.path.getsize(filename)

    if not size or size > fsize:
        size = fsize
    f = open(filename, 'rb')

    if method == "md5":
        hash = md5.new()
    elif method == "sha1":
        hash = sha.new()
    else:
        logging.error("Unknown hash type %s, returning None" % method)
        return None

    while size > 0:
        if chunksize > size:
            chunksize = size
        data = f.read(chunksize)
        if len(data) == 0:
            logging.debug("Nothing left to read but size=%d" % size)
            break
        hash.update(data)
        size -= len(data)
    f.close()
    return hash.hexdigest()


def get_hash_from_file(hash_path, dvd_basename):
    """
    Get the a hash from a given DVD image from a hash file
    (Hash files are usually named MD5SUM or SHA1SUM and are located inside the
    download directories of the DVDs)

    @param hash_path: Local path to a hash file.
    @param cd_image: Basename of a CD image
    """
    hash_file = open(hash_path, 'r')
    for line in hash_file.readlines():
        if dvd_basename in line:
            return line.split()[0]


def unmap_url_cache(cachedir, url, expected_hash, method="md5"):
    """
    Downloads a file from a URL to a cache directory. If the file is already
    at the expected position and has the expected hash, let's not download it
    again.

    @param cachedir: Directory that might hold a copy of the file we want to
            download.
    @param url: URL for the file we want to download.
    @param expected_hash: Hash string that we expect the file downloaded to
            have.
    @param method: Method used to calculate the hash string (md5, sha1).
    """
    # Let's convert cachedir to a canonical path, if it's not already
    cachedir = os.path.realpath(cachedir)
    if not os.path.isdir(cachedir):
        try:
            os.makedirs(cachedir)
        except:
            raise ValueError('Could not create cache directory %s' % cachedir)
    file_from_url = os.path.basename(url)
    file_local_path = os.path.join(cachedir, file_from_url)

    file_hash = None
    failure_counter = 0
    while not file_hash == expected_hash:
        if os.path.isfile(file_local_path):
            if method == "md5":
                file_hash = hash_file(file_local_path, method="md5")
            elif method == "sha1":
                file_hash = hash_file(file_local_path, method="sha1")

            if file_hash == expected_hash:
                # File is already at the expected position and ready to go
                src = file_from_url
            else:
                # Let's download the package again, it's corrupted...
                logging.error("Seems that file %s is corrupted, trying to "
                              "download it again" % file_from_url)
                src = url
                failure_counter += 1
        else:
            # File is not there, let's download it
            src = url
        if failure_counter > 1:
            raise EnvironmentError("Consistently failed to download the "
                                   "package %s. Aborting further download "
                                   "attempts. This might mean either the "
                                   "network connection has problems or the "
                                   "expected hash string that was determined "
                                   "for this file is wrong" % file_from_url)
        file_path = utils.unmap_url(cachedir, src, cachedir)

    return file_path


def run_tests(test_list, job):
    """
    Runs the sequence of KVM tests based on the list of dictionaries
    generated by the configuration system, handling dependencies.

    @param test_list: List with all dictionary test parameters.
    @param job: Autotest job object.

    @return: True, if all tests ran passed, False if any of them failed.
    """
    status_dict = {}

    failed = False
    for dict in test_list:
        if dict.get("skip") == "yes":
            continue
        dependencies_satisfied = True
        for dep in dict.get("depend"):
            for test_name in status_dict.keys():
                if not dep in test_name:
                    continue
                if not status_dict[test_name]:
                    dependencies_satisfied = False
                    break
        if dependencies_satisfied:
            test_iterations = int(dict.get("iterations", 1))
            test_tag = dict.get("shortname")
            # Setting up kvm_stat profiling during test execution.
            # We don't need kvm_stat profiling on the build tests.
            if "build" in test_tag:
                # None because it's the default value on the base_test class
                # and the value None is specifically checked there.
                profile = None
            else:
                profile = True

            if profile:
                job.profilers.add('kvm_stat')
            # We need only one execution, profiled, hence we're passing
            # the profile_only parameter to job.run_test().
            current_status = job.run_test("kvm", params=dict, tag=test_tag,
                                          iterations=test_iterations,
                                          profile_only=profile)
            if profile:
                job.profilers.delete('kvm_stat')

            if not current_status:
                failed = True
        else:
            current_status = False
        status_dict[dict.get("name")] = current_status

    return not failed


def create_report(report_dir, results_dir):
    """
    Creates a neatly arranged HTML results report in the results dir.

    @param report_dir: Directory where the report script is located.
    @param results_dir: Directory where the results will be output.
    """
    reporter = os.path.join(report_dir, 'html_report.py')
    html_file = os.path.join(results_dir, 'results.html')
    os.system('%s -r %s -f %s -R' % (reporter, results_dir, html_file))
