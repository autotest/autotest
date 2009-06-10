import md5, thread, subprocess, time, string, random, socket, os, signal, pty
import select, re, logging
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error

"""
KVM test utility functions.

@copyright: 2008-2009 Red Hat Inc.
"""


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


def get_latest_kvm_release_tag(release_dir):
    """
    Fetches the latest release tag for KVM.

    @param release_dir: KVM source forge download location.
    """
    try:
        page_url = os.path.join(release_dir, "showfiles.php")
        local_web_page = utils.unmap_url("/", page_url, "/tmp")
        f = open(local_web_page, "r")
        data = f.read()
        f.close()
        rx = re.compile("package_id=(\d+).*\>kvm\<", re.IGNORECASE)
        matches = rx.findall(data)
        package_id = matches[0]
        #package_id = 209008
        rx = re.compile("package_id=%s.*release_id=\d+\">(\d+)" % package_id, 
                        re.IGNORECASE)
        matches = rx.findall(data)
        return matches[0] # the first match contains the latest release tag
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


# The following are a class and functions used for SSH, SCP and Telnet
# communication with guests.

class kvm_spawn:
    """
    This class is used for spawning and controlling a child process.
    """

    def __init__(self, command, linesep="\n"):
        """
        Initialize the class and run command as a child process.

        @param command: Command that will be run.
        @param linesep: Line separator for the given platform.
        """
        self.exitstatus = None
        self.linesep = linesep
        (pid, fd) = pty.fork()
        if pid == 0:
            os.execv("/bin/sh", ["/bin/sh", "-c", command])
        else:
            self.pid = pid
            self.fd = fd


    def set_linesep(self, linesep):
        """
        Sets the line separator string (usually "\\n").

        @param linesep: Line separator character.
        """
        self.linesep = linesep


    def is_responsive(self, timeout=5.0):
        """
        Return True if the session is responsive.

        Send a newline to the child process (e.g. SSH or Telnet) and read some
        output using read_nonblocking.
        If all is OK, some output should be available (e.g. the shell prompt).
        In that case return True. Otherwise return False.

        @param timeout: Timeout that will happen before we consider the
                process unresponsive
        """
        self.read_nonblocking(timeout=0.1)
        self.sendline()
        output = self.read_nonblocking(timeout=timeout)
        if output.strip():
            return True
        return False


    def poll(self):
        """
        If the process exited, return its exit status. Otherwise return None.
        The exit status is stored for use in subsequent calls.
        """
        if self.exitstatus != None:
            return self.exitstatus
        pid, status = os.waitpid(self.pid, os.WNOHANG)
        if pid:
            self.exitstatus = os.WEXITSTATUS(status)
            return self.exitstatus
        else:
            return None


    def close(self):
        """
        Close the session (close the process filedescriptors and kills the
        process ID), and return the exit status.
        """
        try:
            os.close(self.fd)
            os.kill(self.pid, signal.SIGTERM)
        except OSError:
            pass
        return self.poll()


    def sendline(self, str=""):
        """
        Sends a string followed by a line separator to the child process.

        @param str: String that will be sent to the child process.
        """
        try:
            os.write(self.fd, str + self.linesep)
        except OSError:
            pass


    def read_nonblocking(self, timeout=1.0):
        """
        Read from child until there is nothing to read for timeout seconds.

        @param timeout: Time (seconds) of wait before we give up reading from
                the child process.
        """
        data = ""
        while True:
            r, w, x = select.select([self.fd], [], [], timeout)
            if self.fd in r:
                try:
                    data += os.read(self.fd, 1024)
                except OSError:
                    return data
            else:
                return data


    def match_patterns(self, str, patterns):
        """
        Match str against a list of patterns.

        Return the index of the first pattern that matches a substring of str.
        None and empty strings in patterns are ignored.
        If no match is found, return None.

        @param patterns: List of strings (regular expression patterns).
        """
        for i in range(len(patterns)):
            if not patterns[i]:
                continue
            exp = re.compile(patterns[i])
            if exp.search(str):
                return i


    def read_until_output_matches(self, patterns, filter=lambda(x):x,
                                  timeout=30.0, internal_timeout=1.0,
                                  print_func=None):
        """
        Read using read_nonblocking until a match is found using match_patterns,
        or until timeout expires. Before attempting to search for a match, the
        data is filtered using the filter function provided.

        @brief: Read from child using read_nonblocking until a pattern
                matches.
        @param patterns: List of strings (regular expression patterns)
        @param filter: Function to apply to the data read from the child before
                attempting to match it against the patterns (should take and
                return a string)
        @param timeout: The duration (in seconds) to wait until a match is
                found
        @param internal_timeout: The timeout to pass to read_nonblocking
        @param print_func: A function to be used to print the data being read
                (should take a string parameter)
        @return: Tuple containing the match index (or None if no match was
                found) and the data read so far.
        """
        match = None
        data = ""

        end_time = time.time() + timeout
        while time.time() < end_time:
            # Read data from child
            newdata = self.read_nonblocking(internal_timeout)
            # Print it if necessary
            if print_func and newdata:
                map(print_func, newdata.splitlines())
            data += newdata

            done = False
            # Look for patterns
            match = self.match_patterns(filter(data), patterns)
            if match != None:
                done = True
            # Check if child has died
            if self.poll() != None:
                logging.debug("Process terminated with status %d", self.poll())
                done = True
            # Are we done?
            if done: break

        # Print some debugging info
        if match == None and self.poll() != 0:
            logging.debug("Timeout elapsed or process terminated. Output: %s",
                          format_str_for_message(data.strip()))

        return (match, data)


    def get_last_word(self, str):
        """
        Return the last word in str.

        @param str: String that will be analyzed.
        """
        if str:
            return str.split()[-1]
        else:
            return ""


    def get_last_line(self, str):
        """
        Return the last non-empty line in str.

        @param str: String that will be analyzed.
        """
        last_line = ""
        for line in str.splitlines():
            if line != "":
                last_line = line
        return last_line


    def read_until_last_word_matches(self, patterns, timeout=30.0,
                                     internal_timeout=1.0, print_func=None):
        """
        Read using read_nonblocking until the last word of the output matches
        one of the patterns (using match_patterns), or until timeout expires.

        @param patterns: A list of strings (regular expression patterns)
        @param timeout: The duration (in seconds) to wait until a match is
                found
        @param internal_timeout: The timeout to pass to read_nonblocking
        @param print_func: A function to be used to print the data being read
                (should take a string parameter)
        @return: A tuple containing the match index (or None if no match was
                found) and the data read so far.
        """
        return self.read_until_output_matches(patterns, self.get_last_word,
                                              timeout, internal_timeout,
                                              print_func)


    def read_until_last_line_matches(self, patterns, timeout=30.0,
                                     internal_timeout=1.0, print_func=None):
        """
        Read using read_nonblocking until the last non-empty line of the output
        matches one of the patterns (using match_patterns), or until timeout
        expires. Return a tuple containing the match index (or None if no match
        was found) and the data read so far.

        @brief: Read using read_nonblocking until the last non-empty line
                matches a pattern.

        @param patterns: A list of strings (regular expression patterns)
        @param timeout: The duration (in seconds) to wait until a match is
                found
        @param internal_timeout: The timeout to pass to read_nonblocking
        @param print_func: A function to be used to print the data being read
                (should take a string parameter)
        """
        return self.read_until_output_matches(patterns, self.get_last_line,
                                              timeout, internal_timeout,
                                              print_func)


    def set_prompt(self, prompt):
        """
        Set the prompt attribute for later use by read_up_to_prompt.

        @param: String that describes the prompt contents.
        """
        self.prompt = prompt


    def read_up_to_prompt(self, timeout=30.0, internal_timeout=1.0,
                          print_func=None):
        """
        Read using read_nonblocking until the last non-empty line of the output
        matches the prompt regular expression set by set_prompt, or until
        timeout expires.

        @brief: Read using read_nonblocking until the last non-empty line
                matches the prompt.

        @param timeout: The duration (in seconds) to wait until a match is
                found
        @param internal_timeout: The timeout to pass to read_nonblocking
        @param print_func: A function to be used to print the data being
                read (should take a string parameter)

        @return: A tuple containing True/False indicating whether the prompt
                was found, and the data read so far.
        """
        (match, output) = self.read_until_last_line_matches([self.prompt],
                                                            timeout,
                                                            internal_timeout,
                                                            print_func)
        if match == None:
            return (False, output)
        else:
            return (True, output)


    def set_status_test_command(self, status_test_command):
        """
        Set the command to be sent in order to get the last exit status.

        @param status_test_command: Command that will be sent to get the last
                exit status.
        """
        self.status_test_command = status_test_command


    def get_command_status_output(self, command, timeout=30.0,
                                  internal_timeout=1.0, print_func=None):
        """
        Send a command and return its exit status and output.

        @param command: Command to send
        @param timeout: The duration (in seconds) to wait until a match is
                found
        @param internal_timeout: The timeout to pass to read_nonblocking
        @param print_func: A function to be used to print the data being read
                (should take a string parameter)

        @return: A tuple (status, output) where status is the exit status or
                None if no exit status is available (e.g. timeout elapsed), and
                output is the output of command.
        """
        # Print some debugging info
        logging.debug("Sending command: %s" % command)

        # Read everything that's waiting to be read
        self.read_nonblocking(0.1)

        # Send the command and get its output
        self.sendline(command)
        (match, output) = self.read_up_to_prompt(timeout, internal_timeout,
                                                 print_func)
        if not match:
            return (None, "\n".join(output.splitlines()[1:]))
        output = "\n".join(output.splitlines()[1:-1])

        # Send the 'echo ...' command to get the last exit status
        self.sendline(self.status_test_command)
        (match, status) = self.read_up_to_prompt(10.0, internal_timeout)
        if not match:
            return (None, output)
        status = int("\n".join(status.splitlines()[1:-1]).strip())

        # Print some debugging info
        if status != 0:
            logging.debug("Command failed; status: %d, output:" % status \
                    + format_str_for_message(output.strip()))

        return (status, output)


    def get_command_status(self, command, timeout=30.0, internal_timeout=1.0,
                           print_func=None):
        """
        Send a command and return its exit status.

        @param command: Command to send
        @param timeout: The duration (in seconds) to wait until a match is
                found
        @param internal_timeout: The timeout to pass to read_nonblocking
        @param print_func: A function to be used to print the data being read
                (should take a string parameter)

        @return: Exit status or None if no exit status is available (e.g.
                timeout elapsed).
        """
        (status, output) = self.get_command_status_output(command, timeout,
                                                          internal_timeout,
                                                          print_func)
        return status


    def get_command_output(self, command, timeout=30.0, internal_timeout=1.0,
                           print_func=None):
        """
        Send a command and return its output.

        @param command: Command to send
        @param timeout: The duration (in seconds) to wait until a match is
                found
        @param internal_timeout: The timeout to pass to read_nonblocking
        @param print_func: A function to be used to print the data being read
                (should take a string parameter)
        """
        (status, output) = self.get_command_status_output(command, timeout,
                                                          internal_timeout,
                                                          print_func)
        return output


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
    sub = kvm_spawn(command, linesep)
    sub.set_prompt(prompt)

    password_prompt_count = 0

    logging.debug("Trying to login...")

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
            kvm_log.debug("Got 'Connection refused'")
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
    sub = kvm_spawn(command)

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
            logging.debug("Timeout or process terminated")
            sub.close()
            return sub.poll() == 0


def scp_to_remote(host, port, username, password, local_path, remote_path,
                  timeout=300):
    """
    Copy files to a remote host (guest).

    @param host: Hostname of the guest
    @param username: User that will be used to copy the files
    @param password: Host's password
    @param local_path: Path on the local machine where we are copying from
    @param remote_path: Path on the remote machine where we are copying to
    @param timeout: Time in seconds that we will wait before giving up to
            copy the files.

    @return: True on success and False on failure.
    """
    command = "scp -o UserKnownHostsFile=/dev/null -r -P %s %s %s@%s:%s" % \
        (port, local_path, username, host, remote_path)
    return remote_scp(command, password, timeout)


def scp_from_remote(host, port, username, password, remote_path, local_path,
                    timeout=300):
    """
    Copy files from a remote host (guest).

    @param host: Hostname of the guest
    @param username: User that will be used to copy the files
    @param password: Host's password
    @param local_path: Path on the local machine where we are copying from
    @param remote_path: Path on the remote machine where we are copying to
    @param timeout: Time in seconds that we will wait before giving up to copy
            the files.

    @return: True on success and False on failure.
    """
    command = "scp -o UserKnownHostsFile=/dev/null -r -P %s %s@%s:%s %s" % \
        (port, username, host, remote_path, local_path)
    return remote_scp(command, password, timeout)


def ssh(host, port, username, password, prompt, timeout=10):
    """
    Log into a remote host (guest) using SSH.

    @param host: Hostname of the guest
    @param username: User that will be used to log into the host.
    @param password: Host's password
    @timeout: Time in seconds that we will wait before giving up on logging
            into the host.

    @return: kvm_spawn object on success and None on failure.
    """
    command = "ssh -o UserKnownHostsFile=/dev/null -p %s %s@%s" % \
        (port, username, host)
    return remote_login(command, password, prompt, "\n", timeout)


def telnet(host, port, username, password, prompt, timeout=10):
    """
    Log into a remote host (guest) using Telnet.

    @param host: Hostname of the guest
    @param username: User that will be used to log into the host.
    @param password: Host's password
    @timeout: Time in seconds that we will wait before giving up on logging
            into the host.

    @return: kvm_spawn object on success and None on failure.
    """
    command = "telnet -l %s %s %s" % (username, host, port)
    return remote_login(command, password, prompt, "\r\n", timeout)


# The following are functions used for running commands in the background.

def track_process(sub, status_output=None, term_func=None, stdout_func=None,
                  prefix=""):
    """
    Read lines from the stdout pipe of the subprocess. Pass each line to
    stdout_func prefixed by prefix. Place the lines in status_output[1].
    When the subprocess exits, call term_func. Place the exit status in
    status_output[0].

    @brief Track a subprocess and report its output and termination.

    @param sub: An object returned by subprocess.Popen
    @param status_output: A list in which the exit status and output are to be
            stored.
    @param term_func: A function to call when the process terminates
            (should take no parameters)
    @param stdout_func: A function to call with each line of output from the
            subprocess (should take a string parameter)

    @param prefix -- a string to pre-pend to each line of the output, before
            passing it to stdout_func
    """
    while True:
        # Read a single line from stdout
        text = sub.stdout.readline()
        # If the subprocess exited...
        if text == "":
            # Get exit code
            status = sub.wait()
            # Report it
            if status_output:
                status_output[0] = status
            # Call term_func
            if term_func:
                term_func()
            return
        # Report the text
        if status_output:
            status_output[1] += text
        # Call stdout_func with the returned text
        if stdout_func:
            text = prefix + text.strip()
            # We need to sanitize the text before passing it to the logging
            # system
            text = text.decode('utf-8', 'replace')
            stdout_func(text)


def run_bg(command, term_func=None, stdout_func=None, prefix="", timeout=1.0):
    """
    Run command as a subprocess. Call stdout_func with each line of output from
    the subprocess (prefixed by prefix). Call term_func when the subprocess
    terminates. If timeout expires and the subprocess is still running, return.

    @brief: Run a subprocess in the background and collect its output and
            exit status.

    @param command: The shell command to execute
    @param term_func: A function to call when the process terminates
            (should take no parameters)
    @param stdout_func: A function to call with each line of output from
            the subprocess (should take a string parameter)
    @param prefix: A string to pre-pend to each line of the output, before
            passing it to stdout_func
    @param timeout: Time duration (in seconds) to wait for the subprocess to
            terminate before returning

    @return: A 3-tuple containing the exit status (None if the subprocess is
            still running), the PID of the subprocess (None if the subprocess
            terminated), and the output collected so far.
    """
    # Start the process
    sub = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT)
    # Start the tracking thread
    status_output = [None, ""]
    thread.start_new_thread(track_process, (sub, status_output, term_func,
                                            stdout_func, prefix))
    # Wait up to timeout secs for the process to exit
    end_time = time.time() + timeout
    while time.time() < end_time:
        # If the process exited, return
        if status_output[0] != None:
            return (status_output[0], None, status_output[1])
        # Otherwise, sleep for a while
        time.sleep(0.1)
    # Report the PID and the output collected so far
    return (None, sub.pid, status_output[1])


# The following are utility functions related to ports.

def is_sshd_running(host, port, timeout=10.0):
    """
    Connect to the given host and port and wait for output.
    Return True if the given host and port are responsive.

    @param host: Host's hostname
    @param port: Host's port
    @param timeout: Time (seconds) before we giving up on checking the SSH
            daemon.

    @return: If output is available, return True. If timeout expires and no
            output was available, return False.
    """
    try:
        # Try to connect
        #s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s = socket.socket()
        s.connect((host, port))
    except socket.error:
        # Can't connect -- return False
        s.close()
        logging.debug("Could not connect")
        return False
    s.setblocking(False)
    # Wait up to 'timeout' seconds
    end_time = time.time() + timeout
    while time.time() < end_time:
        try:
            time.sleep(0.1)
            # Try to receive some text
            str = s.recv(1024)
            if len(str) > 0:
                s.shutdown(socket.SHUT_RDWR)
                s.close()
                logging.debug("Success! got string %r" % str)
                return True
        except socket.error:
            # No text was available; try again
            pass
    # Timeout elapsed and no text was received
    s.shutdown(socket.SHUT_RDWR)
    s.close()
    logging.debug("Timeout")
    return False


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

def generate_random_string(length):
    """
    Return a random string using alphanumeric characters.

    @length: length of the string that will be generated.
    """
    str = ""
    chars = string.letters + string.digits
    while length > 0:
        str += random.choice(chars)
        length -= 1
    return str


def format_str_for_message(str):
    """
    Format str so that it can be appended to a message.
    If str consists of one line, prefix it with a space.
    If str consists of multiple lines, prefix it with a newline.

    @param str: string that will be formatted.
    """
    num_lines = len(str.splitlines())
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


def md5sum_file(filename, size=None):
    """
    Calculate the md5sum of filename.
    If size is not None, limit to first size bytes.
    Throw exception if something is wrong with filename.
    Can be also implemented with bash one-liner (assuming size%1024==0):
    dd if=filename bs=1024 count=size/1024 | md5sum -

    @param filename: Path of the file that will have its md5sum calculated.
    @param returns: md5sum of the file.
    """
    chunksize = 4096
    fsize = os.path.getsize(filename)
    if not size or size>fsize:
        size = fsize
    f = open(filename, 'rb')
    o = md5.new()
    while size > 0:
        if chunksize > size:
            chunksize = size
        data = f.read(chunksize)
        if len(data) == 0:
            logging.debug("Nothing left to read but size=%d" % size)
            break
        o.update(data)
        size -= len(data)
    f.close()
    return o.hexdigest()
