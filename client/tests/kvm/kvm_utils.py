"""
KVM test utility functions.

@copyright: 2008-2009 Red Hat Inc.
"""

import time, string, random, socket, os, signal, re, logging, commands, cPickle
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error, logging_config
import kvm_subprocess


def dump_env(obj, filename):
    """
    Dump KVM test environment to a file.

    @param filename: Path to a file where the environment will be dumped to.
    """
    file = open(filename, "w")
    cPickle.dump(obj, file)
    file.close()


def load_env(filename, default={}):
    """
    Load KVM test environment from an environment file.

    @param filename: Path to a file where the environment was dumped to.
    """
    try:
        file = open(filename, "r")
        obj = cPickle.load(file)
        file.close()
        return obj
    # Almost any exception can be raised during unpickling, so let's catch
    # them all
    except Exception, e:
        logging.warn(e)
        return default


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


def get_sub_pool(dict, piece, num_pieces):
    """
    Split a MAC-IP pool and return a single requested piece.

    For example, get_sub_pool(dict, 0, 3) will split the pool in 3 pieces and
    return a dict representing the first piece.

    @param dict: A dict that contains pool parameters.
    @param piece: The index of the requested piece.  Should range from 0 to
        num_pieces - 1.
    @param num_pieces: The total number of pieces.
    @return: A copy of dict, modified to describe the requested sub-pool.
    """
    range_dicts = [get_sub_dict(dict, name) for name in
                   get_sub_dict_names(dict, "address_ranges")]
    if not range_dicts:
        return dict
    ranges = [[d.get("address_range_base_mac"),
               d.get("address_range_base_ip"),
               int(d.get("address_range_size", 1))] for d in range_dicts]
    total_size = sum(r[2] for r in ranges)
    base = total_size * piece / num_pieces
    size = total_size * (piece + 1) / num_pieces - base

    # Find base of current sub-pool
    for i in range(len(ranges)):
        r = ranges[i]
        if base < r[2]:
            r[0] = r[0] and offset_mac(r[0], base)
            r[1] = r[1] and offset_ip(r[1], base)
            r[2] -= base
            break
        base -= r[2]

    # Collect ranges up to end of current sub-pool
    new_ranges = []
    for i in range(i, len(ranges)):
        r = ranges[i]
        new_ranges.append(r)
        if size <= r[2]:
            r[2] = size
            break
        size -= r[2]

    # Write new dict
    new_dict = dict.copy()
    new_dict["address_ranges"] = " ".join("r%d" % i for i in
                                          range(len(new_ranges)))
    for i in range(len(new_ranges)):
        new_dict["address_range_base_mac_r%d" % i] = new_ranges[i][0]
        new_dict["address_range_base_ip_r%d" % i] = new_ranges[i][1]
        new_dict["address_range_size_r%d" % i] = new_ranges[i][2]
    return new_dict


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
    logging.info("Fetching git [REP '%s' BRANCH '%s' COMMIT '%s'] -> %s",
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
    try:
        desc = "tag %s" % utils.system_output("git describe")
    except error.CmdError:
        desc = "no tag found"

    logging.info("Commit hash for %s is %s (%s)" % (repository, h.strip(),
                                                    desc))
    return srcdir


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
                 r"[Cc]onnection.*closed", r"[Cc]onnection.*refused",
                 r"[Pp]lease wait", prompt],
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
        elif match == 5:  # "Please wait"
            logging.debug("Got 'Please wait'")
            timeout = 30
            continue
        elif match == 6:  # prompt
            logging.debug("Got shell prompt -- logged in")
            return sub
        else:  # match == None
            logging.debug("Timeout elapsed or process terminated")
            sub.close()
            return None


def remote_scp(command, password, transfer_timeout=600, login_timeout=10):
    """
    Run the given command using kvm_spawn and provide answers to the questions
    asked. If transfer_timeout expires while waiting for the transfer to
    complete, fail. If login_timeout expires while waiting for output from the
    child (e.g. a password prompt), fail.

    @brief: Transfer files using SCP, given a command line.

    @param command: The command to execute
        (e.g. "scp -r foobar root@localhost:/tmp/").
    @param password: The password to send in reply to a password prompt.
    @param transfer_timeout: The time duration (in seconds) to wait for the
        transfer to complete.
    @param login_timeout: The maximal time duration (in seconds) to wait for
        each step of the login procedure (i.e. the "Are you sure" prompt or the
        password prompt)

    @return: True if the transfer succeeds and False on failure.
    """
    sub = kvm_subprocess.kvm_expect(command)

    password_prompt_count = 0
    timeout = login_timeout

    logging.debug("Trying to SCP with command '%s', login timeout %ds, "
                  "transfer timeout %ds", command, login_timeout,
                  transfer_timeout)

    while True:
        (match, text) = sub.read_until_last_line_matches(
                [r"[Aa]re you sure", r"[Pp]assword:\s*$", r"lost connection"],
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
                timeout = transfer_timeout
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
            if sub.is_alive():
                logging.debug("Timeout expired")
                sub.close()
                return False
            else:
                status = sub.get_status()
                sub.close()
                logging.debug("SCP process terminated with status %s", status)
                return status == 0


def scp_to_remote(host, port, username, password, local_path, remote_path,
                  timeout=600):
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
    command = ("scp -v -o UserKnownHostsFile=/dev/null "
               "-o PreferredAuthentications=password -r -P %s %s %s@%s:%s" %
               (port, local_path, username, host, remote_path))
    return remote_scp(command, password, timeout)


def scp_from_remote(host, port, username, password, remote_path, local_path,
                    timeout=600):
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
    command = ("scp -v -o UserKnownHostsFile=/dev/null "
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
    Return a host free port in the range [start_port, end_port].

    @param start_port: First port that will be checked.
    @param end_port: Port immediately after the last one that will be checked.
    """
    for i in range(start_port, end_port):
        if is_port_free(i):
            return i
    return None


def find_free_ports(start_port, end_port, count):
    """
    Return count of host free ports in the range [start_port, end_port].

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


# An easy way to log lines to files when the logging system can't be used

_open_log_files = {}
_log_file_dir = "/tmp"


def log_line(filename, line):
    """
    Write a line to a file.  '\n' is appended to the line.

    @param filename: Path of file to write to, either absolute or relative to
            the dir set by set_log_file_dir().
    @param line: Line to write.
    """
    global _open_log_files, _log_file_dir
    if filename not in _open_log_files:
        path = get_path(_log_file_dir, filename)
        try:
            os.makedirs(os.path.dirname(path))
        except OSError:
            pass
        _open_log_files[filename] = open(path, "w")
    timestr = time.strftime("%Y-%m-%d %H:%M:%S")
    _open_log_files[filename].write("%s: %s\n" % (timestr, line))
    _open_log_files[filename].flush()


def set_log_file_dir(dir):
    """
    Set the base directory for log files created by log_line().

    @param dir: Directory for log files.
    """
    global _log_file_dir
    _log_file_dir = dir


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


def generate_tmp_file_name(file, ext=None, dir='/tmp/'):
    """
    Returns a temporary file name. The file is not created.
    """
    while True:
        file_name = (file + '-' + time.strftime("%Y%m%d-%H%M%S-") +
                     generate_random_string(4))
        if ext:
            file_name += '.' + ext
        file_name = os.path.join(dir, file_name)
        if not os.path.exists(file_name):
            break

    return file_name


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
            # Setting up profilers during test execution.
            profilers = dict.get("profilers", "").split()
            for profiler in profilers:
                job.profilers.add(profiler)

            # We need only one execution, profiled, hence we're passing
            # the profile_only parameter to job.run_test().
            current_status = job.run_test("kvm", params=dict, tag=test_tag,
                                          iterations=test_iterations,
                                          profile_only= bool(profilers) or None)

            for profiler in profilers:
                job.profilers.delete(profiler)

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


def get_full_pci_id(pci_id):
    """
    Get full PCI ID of pci_id.

    @param pci_id: PCI ID of a device.
    """
    cmd = "lspci -D | awk '/%s/ {print $1}'" % pci_id
    status, full_id = commands.getstatusoutput(cmd)
    if status != 0:
        return None
    return full_id


def get_vendor_from_pci_id(pci_id):
    """
    Check out the device vendor ID according to pci_id.

    @param pci_id: PCI ID of a device.
    """
    cmd = "lspci -n | awk '/%s/ {print $3}'" % pci_id
    return re.sub(":", " ", commands.getoutput(cmd))


class KvmLoggingConfig(logging_config.LoggingConfig):
    """
    Used with the sole purpose of providing convenient logging setup
    for the KVM test auxiliary programs.
    """
    def configure_logging(self, results_dir=None, verbose=False):
        super(KvmLoggingConfig, self).configure_logging(use_console=True,
                                                        verbose=verbose)


class PciAssignable(object):
    """
    Request PCI assignable devices on host. It will check whether to request
    PF (physical Functions) or VF (Virtual Functions).
    """
    def __init__(self, type="vf", driver=None, driver_option=None,
                 names=None, devices_requested=None):
        """
        Initialize parameter 'type' which could be:
        vf: Virtual Functions
        pf: Physical Function (actual hardware)
        mixed:  Both includes VFs and PFs

        If pass through Physical NIC cards, we need to specify which devices
        to be assigned, e.g. 'eth1 eth2'.

        If pass through Virtual Functions, we need to specify how many vfs
        are going to be assigned, e.g. passthrough_count = 8 and max_vfs in
        config file.

        @param type: PCI device type.
        @param driver: Kernel module for the PCI assignable device.
        @param driver_option: Module option to specify the maximum number of
                VFs (eg 'max_vfs=7')
        @param names: Physical NIC cards correspondent network interfaces,
                e.g.'eth1 eth2 ...'
        @param devices_requested: Number of devices being requested.
        """
        self.type = type
        self.driver = driver
        self.driver_option = driver_option
        if names:
            self.name_list = names.split()
        if devices_requested:
            self.devices_requested = int(devices_requested)
        else:
            self.devices_requested = None


    def _get_pf_pci_id(self, name, search_str):
        """
        Get the PF PCI ID according to name.

        @param name: Name of the PCI device.
        @param search_str: Search string to be used on lspci.
        """
        cmd = "ethtool -i %s | awk '/bus-info/ {print $2}'" % name
        s, pci_id = commands.getstatusoutput(cmd)
        if not (s or "Cannot get driver information" in pci_id):
            return pci_id[5:]
        cmd = "lspci | awk '/%s/ {print $1}'" % search_str
        pci_ids = [id for id in commands.getoutput(cmd).splitlines()]
        nic_id = int(re.search('[0-9]+', name).group(0))
        if (len(pci_ids) - 1) < nic_id:
            return None
        return pci_ids[nic_id]


    def _release_dev(self, pci_id):
        """
        Release a single PCI device.

        @param pci_id: PCI ID of a given PCI device.
        """
        base_dir = "/sys/bus/pci"
        full_id = get_full_pci_id(pci_id)
        vendor_id = get_vendor_from_pci_id(pci_id)
        drv_path = os.path.join(base_dir, "devices/%s/driver" % full_id)
        if 'pci-stub' in os.readlink(drv_path):
            cmd = "echo '%s' > %s/new_id" % (vendor_id, drv_path)
            if os.system(cmd):
                return False

            stub_path = os.path.join(base_dir, "drivers/pci-stub")
            cmd = "echo '%s' > %s/unbind" % (full_id, stub_path)
            if os.system(cmd):
                return False

            driver = self.dev_drivers[pci_id]
            cmd = "echo '%s' > %s/bind" % (full_id, driver)
            if os.system(cmd):
                return False

        return True


    def get_vf_devs(self):
        """
        Catch all VFs PCI IDs.

        @return: List with all PCI IDs for the Virtual Functions avaliable
        """
        if not self.sr_iov_setup():
            return []

        cmd = "lspci | awk '/Virtual Function/ {print $1}'"
        return commands.getoutput(cmd).split()


    def get_pf_devs(self):
        """
        Catch all PFs PCI IDs.

        @return: List with all PCI IDs for the physical hardware requested
        """
        pf_ids = []
        for name in self.name_list:
            pf_id = self._get_pf_pci_id(name, "Ethernet")
            if not pf_id:
                continue
            pf_ids.append(pf_id)
        return pf_ids


    def get_devs(self, count):
        """
        Check out all devices' PCI IDs according to their name.

        @param count: count number of PCI devices needed for pass through
        @return: a list of all devices' PCI IDs
        """
        if self.type == "vf":
            vf_ids = self.get_vf_devs()
        elif self.type == "pf":
            vf_ids = self.get_pf_devs()
        elif self.type == "mixed":
            vf_ids = self.get_vf_devs()
            vf_ids.extend(self.get_pf_devs())
        return vf_ids[0:count]


    def get_vfs_count(self):
        """
        Get VFs count number according to lspci.
        """
        # FIXME: Need to think out a method of identify which
        # 'virtual function' belongs to which physical card considering
        # that if the host has more than one 82576 card. PCI_ID?
        cmd = "lspci | grep 'Virtual Function' | wc -l"
        return int(commands.getoutput(cmd))


    def check_vfs_count(self):
        """
        Check VFs count number according to the parameter driver_options.
        """
        # Network card 82576 has two network interfaces and each can be
        # virtualized up to 7 virtual functions, therefore we multiply
        # two for the value of driver_option 'max_vfs'.
        expected_count = int((re.findall("(\d)", self.driver_option)[0])) * 2
        return (self.get_vfs_count == expected_count)


    def is_binded_to_stub(self, full_id):
        """
        Verify whether the device with full_id is already binded to pci-stub.

        @param full_id: Full ID for the given PCI device
        """
        base_dir = "/sys/bus/pci"
        stub_path = os.path.join(base_dir, "drivers/pci-stub")
        if os.path.exists(os.path.join(stub_path, full_id)):
            return True
        return False


    def sr_iov_setup(self):
        """
        Ensure the PCI device is working in sr_iov mode.

        Check if the PCI hardware device drive is loaded with the appropriate,
        parameters (number of VFs), and if it's not, perform setup.

        @return: True, if the setup was completed successfuly, False otherwise.
        """
        re_probe = False
        s, o = commands.getstatusoutput('lsmod | grep %s' % self.driver)
        if s:
            re_probe = True
        elif not self.check_vfs_count():
            os.system("modprobe -r %s" % self.driver)
            re_probe = True
        else:
            return True

        # Re-probe driver with proper number of VFs
        if re_probe:
            cmd = "modprobe %s %s" % (self.driver, self.driver_option)
            logging.info("Loading the driver '%s' with option '%s'" %
                                   (self.driver, self.driver_option))
            s, o = commands.getstatusoutput(cmd)
            if s:
                return False
            return True


    def request_devs(self):
        """
        Implement setup process: unbind the PCI device and then bind it
        to the pci-stub driver.

        @return: a list of successfully requested devices' PCI IDs.
        """
        base_dir = "/sys/bus/pci"
        stub_path = os.path.join(base_dir, "drivers/pci-stub")

        self.pci_ids = self.get_devs(self.devices_requested)
        logging.debug("The following pci_ids were found: %s", self.pci_ids)
        requested_pci_ids = []
        self.dev_drivers = {}

        # Setup all devices specified for assignment to guest
        for pci_id in self.pci_ids:
            full_id = get_full_pci_id(pci_id)
            if not full_id:
                continue
            drv_path = os.path.join(base_dir, "devices/%s/driver" % full_id)
            dev_prev_driver= os.path.realpath(os.path.join(drv_path,
                                              os.readlink(drv_path)))
            self.dev_drivers[pci_id] = dev_prev_driver

            # Judge whether the device driver has been binded to stub
            if not self.is_binded_to_stub(full_id):
                logging.debug("Binding device %s to stub", full_id)
                vendor_id = get_vendor_from_pci_id(pci_id)
                stub_new_id = os.path.join(stub_path, 'new_id')
                unbind_dev = os.path.join(drv_path, 'unbind')
                stub_bind = os.path.join(stub_path, 'bind')

                info_write_to_files = [(vendor_id, stub_new_id),
                                       (full_id, unbind_dev),
                                       (full_id, stub_bind)]

                for content, file in info_write_to_files:
                    try:
                        utils.open_write_close(file, content)
                    except IOError:
                        logging.debug("Failed to write %s to file %s", content,
                                      file)
                        continue

                if not self.is_binded_to_stub(full_id):
                    logging.error("Binding device %s to stub failed", pci_id)
                    continue
            else:
                logging.debug("Device %s already binded to stub", pci_id)
            requested_pci_ids.append(pci_id)
        self.pci_ids = requested_pci_ids
        return self.pci_ids


    def release_devs(self):
        """
        Release all PCI devices currently assigned to VMs back to the
        virtualization host.
        """
        try:
            for pci_id in self.dev_drivers:
                if not self._release_dev(pci_id):
                    logging.error("Failed to release device %s to host", pci_id)
                else:
                    logging.info("Released device %s successfully", pci_id)
        except:
            return
