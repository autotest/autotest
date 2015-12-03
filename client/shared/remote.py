"""
Functions and classes used for logging into guests and transferring files.
"""
import logging
import os
import re
import shutil
import tempfile
import time

import aexpect

import data_dir
import error
import rss_client
import utils


class LoginError(Exception):

    def __init__(self, msg, output):
        Exception.__init__(self, msg, output)
        self.msg = msg
        self.output = output

    def __str__(self):
        return "%s    (output: %r)" % (self.msg, self.output)


class LoginAuthenticationError(LoginError):
    pass


class LoginTimeoutError(LoginError):

    def __init__(self, output):
        LoginError.__init__(self, "Login timeout expired", output)


class LoginProcessTerminatedError(LoginError):

    def __init__(self, status, output):
        LoginError.__init__(self, None, output)
        self.status = status

    def __str__(self):
        return ("Client process terminated    (status: %s,    output: %r)" %
                (self.status, self.output))


class LoginBadClientError(LoginError):

    def __init__(self, client):
        LoginError.__init__(self, None, None)
        self.client = client

    def __str__(self):
        return "Unknown remote shell client: %r" % self.client


class SCPError(Exception):

    def __init__(self, msg, output):
        Exception.__init__(self, msg, output)
        self.msg = msg
        self.output = output

    def __str__(self):
        return "%s    (output: %r)" % (self.msg, self.output)


class SCPAuthenticationError(SCPError):
    pass


class SCPAuthenticationTimeoutError(SCPAuthenticationError):

    def __init__(self, output):
        SCPAuthenticationError.__init__(self, "Authentication timeout expired",
                                        output)


class SCPTransferTimeoutError(SCPError):

    def __init__(self, output):
        SCPError.__init__(self, "Transfer timeout expired", output)


class SCPTransferFailedError(SCPError):

    def __init__(self, status, output):
        SCPError.__init__(self, None, output)
        self.status = status

    def __str__(self):
        return ("SCP transfer failed    (status: %s,    output: %r)" %
                (self.status, self.output))


def handle_prompts(session, username, password, prompt, timeout=10,
                   debug=False):
    """
    Connect to a remote host (guest) using SSH or Telnet or other else.
    Wait for questions and provide answers.  If timeout expires while
    waiting for output from the child (e.g. a password prompt or
    a shell prompt) -- fail.

    @brief: Connect to a remote host (guest) using SSH or Telnet or else.

    :param session: An Expect or ShellSession instance to operate on
    :param username: The username to send in reply to a login prompt
    :param password: The password to send in reply to a password prompt
    :param prompt: The shell prompt that indicates a successful login
    :param timeout: The maximal time duration (in seconds) to wait for each
            step of the login procedure (i.e. the "Are you sure" prompt, the
            password prompt, the shell prompt, etc)
    :raise LoginTimeoutError: If timeout expires
    :raise LoginAuthenticationError: If authentication fails
    :raise LoginProcessTerminatedError: If the client terminates during login
    :raise LoginError: If some other error occurs
    """
    password_prompt_count = 0
    login_prompt_count = 0

    while True:
        try:
            match, text = session.read_until_last_line_matches(
                [r"[Aa]re you sure", r"[Pp]assword:\s*",
                 r"(?<![Ll]ast).*[Ll]ogin:\s*$",  # Don't match "Last Login:"
                 r"[Cc]onnection.*closed", r"[Cc]onnection.*refused",
                 r"[Pp]lease wait", r"[Ww]arning", r"[Ee]nter.*username",
                 r"[Ee]nter.*password", prompt],
                timeout=timeout, internal_timeout=0.5)
            if match == 0:  # "Are you sure you want to continue connecting"
                if debug:
                    logging.debug("Got 'Are you sure...', sending 'yes'")
                session.sendline("yes")
                continue
            elif match == 1 or match == 8:  # "password:"
                if password_prompt_count == 0:
                    if debug:
                        logging.debug("Got password prompt, sending '%s'",
                                      password)
                    session.sendline(password)
                    password_prompt_count += 1
                    continue
                else:
                    raise LoginAuthenticationError("Got password prompt twice",
                                                   text)
            elif match == 2 or match == 7:  # "login:"
                if login_prompt_count == 0 and password_prompt_count == 0:
                    if debug:
                        logging.debug("Got username prompt; sending '%s'",
                                      username)
                    session.sendline(username)
                    login_prompt_count += 1
                    continue
                else:
                    if login_prompt_count > 0:
                        msg = "Got username prompt twice"
                    else:
                        msg = "Got username prompt after password prompt"
                    raise LoginAuthenticationError(msg, text)
            elif match == 3:  # "Connection closed"
                raise LoginError("Client said 'connection closed'", text)
            elif match == 4:  # "Connection refused"
                raise LoginError("Client said 'connection refused'", text)
            elif match == 5:  # "Please wait"
                if debug:
                    logging.debug("Got 'Please wait'")
                timeout = 30
                continue
            elif match == 6:  # "Warning added RSA"
                if debug:
                    logging.debug("Got 'Warning added RSA to known host list")
                continue
            elif match == 9:  # prompt
                if debug:
                    logging.debug("Got shell prompt -- logged in")
                break
        except aexpect.ExpectTimeoutError, e:
            raise LoginTimeoutError(e.output)
        except aexpect.ExpectProcessTerminatedError, e:
            raise LoginProcessTerminatedError(e.status, e.output)


def remote_login(client, host, port, username, password, prompt, linesep="\n",
                 log_filename=None, timeout=10, interface=None):
    """
    Log into a remote host (guest) using SSH/Telnet/Netcat.

    :param client: The client to use ('ssh', 'telnet' or 'nc')
    :param host: Hostname or IP address
    :param port: Port to connect to
    :param username: Username (if required)
    :param password: Password (if required)
    :param prompt: Shell prompt (regular expression)
    :param linesep: The line separator to use when sending lines
            (e.g. '\\n' or '\\r\\n')
    :param log_filename: If specified, log all output to this file
    :param timeout: The maximal time duration (in seconds) to wait for
            each step of the login procedure (i.e. the "Are you sure" prompt
            or the password prompt)
    :interface: The interface the neighbours attach to (only use when using ipv6
                linklocal address.)
    :raise LoginError: If using ipv6 linklocal but not assign a interface that
                       the neighbour attache
    :raise LoginBadClientError: If an unknown client is requested
    :raise: Whatever handle_prompts() raises
    :return: A ShellSession object.
    """
    if host and host.lower().startswith("fe80"):
        if not interface:
            raise LoginError("When using ipv6 linklocal an interface must "
                             "be assigned")
        host = "%s%%%s" % (host, interface)
    if client == "ssh":
        cmd = ("ssh -o UserKnownHostsFile=/dev/null "
               "-o PreferredAuthentications=password -p %s %s@%s" %
               (port, username, host))
    elif client == "telnet":
        cmd = "telnet -l %s %s %s" % (username, host, port)
    elif client == "nc":
        cmd = "nc %s %s" % (host, port)
    else:
        raise LoginBadClientError(client)

    logging.debug("Login command: '%s'", cmd)
    session = aexpect.ShellSession(cmd, linesep=linesep, prompt=prompt)
    try:
        handle_prompts(session, username, password, prompt, timeout)
    except Exception:
        session.close()
        raise
    if log_filename:
        session.set_output_func(utils.log_line)
        session.set_output_params((log_filename,))
        session.set_log_file(log_filename)
    return session


def wait_for_login(client, host, port, username, password, prompt,
                   linesep="\n", log_filename=None, timeout=240,
                   internal_timeout=10, interface=None):
    """
    Make multiple attempts to log into a remote host (guest) until one succeeds
    or timeout expires.

    :param timeout: Total time duration to wait for a successful login
    :param internal_timeout: The maximal time duration (in seconds) to wait for
            each step of the login procedure (e.g. the "Are you sure" prompt
            or the password prompt)
    :interface: The interface the neighbours attach to (only use when using ipv6
                linklocal address.)
    :see:: remote_login()
    :raise: Whatever remote_login() raises
    :return: A ShellSession object.
    """
    logging.debug("Attempting to log into %s:%s using %s (timeout %ds)",
                  host, port, client, timeout)
    end_time = time.time() + timeout
    while time.time() < end_time:
        try:
            return remote_login(client, host, port, username, password, prompt,
                                linesep, log_filename, internal_timeout,
                                interface)
        except LoginError, e:
            logging.debug(e)
        time.sleep(2)
    # Timeout expired; try one more time but don't catch exceptions
    return remote_login(client, host, port, username, password, prompt,
                        linesep, log_filename, internal_timeout, interface)


def _remote_scp(session, password_list, transfer_timeout=600, login_timeout=20):
    """
    Transfer file(s) to a remote host (guest) using SCP.  Wait for questions
    and provide answers.  If login_timeout expires while waiting for output
    from the child (e.g. a password prompt), fail.  If transfer_timeout expires
    while waiting for the transfer to complete, fail.

    @brief: Transfer files using SCP, given a command line.

    :param session: An Expect or ShellSession instance to operate on
    :param password_list: Password list to send in reply to the password prompt
    :param transfer_timeout: The time duration (in seconds) to wait for the
            transfer to complete.
    :param login_timeout: The maximal time duration (in seconds) to wait for
            each step of the login procedure (i.e. the "Are you sure" prompt or
            the password prompt)
    :raise SCPAuthenticationError: If authentication fails
    :raise SCPTransferTimeoutError: If the transfer fails to complete in time
    :raise SCPTransferFailedError: If the process terminates with a nonzero
            exit code
    :raise SCPError: If some other error occurs
    """
    password_prompt_count = 0
    timeout = login_timeout
    authentication_done = False

    scp_type = len(password_list)

    while True:
        try:
            match, text = session.read_until_last_line_matches(
                [r"[Aa]re you sure", r"[Pp]assword:\s*$", r"lost connection"],
                timeout=timeout, internal_timeout=0.5)
            if match == 0:  # "Are you sure you want to continue connecting"
                logging.debug("Got 'Are you sure...', sending 'yes'")
                session.sendline("yes")
                continue
            elif match == 1:  # "password:"
                if password_prompt_count == 0:
                    logging.debug("Got password prompt, sending '%s'" %
                                  password_list[password_prompt_count])
                    session.sendline(password_list[password_prompt_count])
                    password_prompt_count += 1
                    timeout = transfer_timeout
                    if scp_type == 1:
                        authentication_done = True
                    continue
                elif password_prompt_count == 1 and scp_type == 2:
                    logging.debug("Got password prompt, sending '%s'" %
                                  password_list[password_prompt_count])
                    session.sendline(password_list[password_prompt_count])
                    password_prompt_count += 1
                    timeout = transfer_timeout
                    authentication_done = True
                    continue
                else:
                    raise SCPAuthenticationError("Got password prompt twice",
                                                 text)
            elif match == 2:  # "lost connection"
                raise SCPError("SCP client said 'lost connection'", text)
        except aexpect.ExpectTimeoutError, e:
            if authentication_done:
                raise SCPTransferTimeoutError(e.output)
            else:
                raise SCPAuthenticationTimeoutError(e.output)
        except aexpect.ExpectProcessTerminatedError, e:
            if e.status == 0:
                logging.debug("SCP process terminated with status 0")
                break
            else:
                raise SCPTransferFailedError(e.status, e.output)


def remote_scp(command, password_list, log_filename=None, transfer_timeout=600,
               login_timeout=20):
    """
    Transfer file(s) to a remote host (guest) using SCP.

    @brief: Transfer files using SCP, given a command line.

    :param command: The command to execute
        (e.g. "scp -r foobar root@localhost:/tmp/").
    :param password_list: Password list to send in reply to a password prompt.
    :param log_filename: If specified, log all output to this file
    :param transfer_timeout: The time duration (in seconds) to wait for the
            transfer to complete.
    :param login_timeout: The maximal time duration (in seconds) to wait for
            each step of the login procedure (i.e. the "Are you sure" prompt
            or the password prompt)
    :raise: Whatever _remote_scp() raises
    """
    logging.debug("Trying to SCP with command '%s', timeout %ss",
                  command, transfer_timeout)
    if log_filename:
        output_func = utils.log_line
        output_params = (log_filename,)
    else:
        output_func = None
        output_params = ()
    session = aexpect.Expect(command,
                             output_func=output_func,
                             output_params=output_params)
    try:
        _remote_scp(session, password_list, transfer_timeout, login_timeout)
    finally:
        session.close()


def scp_to_remote(host, port, username, password, local_path, remote_path,
                  limit="", log_filename=None, timeout=600, interface=None):
    """
    Copy files to a remote host (guest) through scp.

    :param host: Hostname or IP address
    :param username: Username (if required)
    :param password: Password (if required)
    :param local_path: Path on the local machine where we are copying from
    :param remote_path: Path on the remote machine where we are copying to
    :param limit: Speed limit of file transfer.
    :param log_filename: If specified, log all output to this file
    :param timeout: The time duration (in seconds) to wait for the transfer
            to complete.
    :interface: The interface the neighbours attach to (only use when using ipv6
                linklocal address.)
    :raise: Whatever remote_scp() raises
    """
    if (limit):
        limit = "-l %s" % (limit)

    if host and host.lower().startswith("fe80"):
        if not interface:
            raise SCPError("When using ipv6 linklocal address must assign",
                           "the interface the neighbour attache")
        host = "%s%%%s" % (host, interface)

    command = ("scp -v -o UserKnownHostsFile=/dev/null "
               "-o PreferredAuthentications=password -r %s "
               "-P %s %s %s@\[%s\]:%s" %
               (limit, port, local_path, username, host, remote_path))
    password_list = []
    password_list.append(password)
    return remote_scp(command, password_list, log_filename, timeout)


def scp_from_remote(host, port, username, password, remote_path, local_path,
                    limit="", log_filename=None, timeout=600, interface=None):
    """
    Copy files from a remote host (guest).

    :param host: Hostname or IP address
    :param username: Username (if required)
    :param password: Password (if required)
    :param local_path: Path on the local machine where we are copying from
    :param remote_path: Path on the remote machine where we are copying to
    :param limit: Speed limit of file transfer.
    :param log_filename: If specified, log all output to this file
    :param timeout: The time duration (in seconds) to wait for the transfer
            to complete.
    :interface: The interface the neighbours attach to (only use when using ipv6
                linklocal address.)
    :raise: Whatever remote_scp() raises
    """
    if (limit):
        limit = "-l %s" % (limit)
    if host and host.lower().startswith("fe80"):
        if not interface:
            raise SCPError("When using ipv6 linklocal address must assign, ",
                           "the interface the neighbour attache")
        host = "%s%%%s" % (host, interface)

    command = ("scp -v -o UserKnownHostsFile=/dev/null "
               "-o PreferredAuthentications=password -r %s "
               "-P %s %s@\[%s\]:%s %s" %
               (limit, port, username, host, remote_path, local_path))
    password_list = []
    password_list.append(password)
    remote_scp(command, password_list, log_filename, timeout)


def scp_between_remotes(src, dst, port, s_passwd, d_passwd, s_name, d_name,
                        s_path, d_path, limit="", log_filename=None,
                        timeout=600, src_inter=None, dst_inter=None):
    """
    Copy files from a remote host (guest) to another remote host (guest).

    :param src/dst: Hostname or IP address of src and dst
    :param s_name/d_name: Username (if required)
    :param s_passwd/d_passwd: Password (if required)
    :param s_path/d_path: Path on the remote machine where we are copying
                         from/to
    :param limit: Speed limit of file transfer.
    :param log_filename: If specified, log all output to this file
    :param timeout: The time duration (in seconds) to wait for the transfer
            to complete.
    :src_inter: The interface on local that the src neighbour attache
    :dst_inter: The interface on the src that the dst neighbour attache

    :return: True on success and False on failure.
    """
    if (limit):
        limit = "-l %s" % (limit)
    if src and src.lower().startswith("fe80"):
        if not src_inter:
            raise SCPError("When using ipv6 linklocal address must assign ",
                           "the interface the neighbour attache")
        src = "%s%%%s" % (src, src_inter)
    if dst and dst.lower().startswith("fe80"):
        if not dst_inter:
            raise SCPError("When using ipv6 linklocal address must assign ",
                           "the interface the neighbour attache")
        dst = "%s%%%s" % (dst, dst_inter)

    command = ("scp -v -o UserKnownHostsFile=/dev/null "
               "-o PreferredAuthentications=password -r %s -P %s"
               " %s@\[%s\]:%s %s@\[%s\]:%s" %
               (limit, port, s_name, src, s_path, d_name, dst, d_path))
    password_list = []
    password_list.append(s_passwd)
    password_list.append(d_passwd)
    return remote_scp(command, password_list, log_filename, timeout)


def nc_copy_between_remotes(src, dst, s_port, s_passwd, d_passwd,
                            s_name, d_name, s_path, d_path,
                            c_type="ssh", c_prompt="\n",
                            d_port="8888", d_protocol="udp", timeout=10,
                            check_sum=True):
    """
    Copy files from a remote host (guest) to another remote host (guest) using
    netcat. now this method only support linux

    :param src/dst: Hostname or IP address of src and dst
    :param s_name/d_name: Username (if required)
    :param s_passwd/d_passwd: Password (if required)
    :param s_path/d_path: Path on the remote machine where we are copying
    :param c_type: Login method to remote host(guest).
    :param c_prompt : command line prompt of remote host(guest)
    :param d_port:  the port data transfer
    :param d_protocol : nc protocol use (tcp or udp)
    :param timeout: If a connection and stdin are idle for more than timeout
                    seconds, then the connection is silently closed.

    :return: True on success and False on failure.
    """
    s_session = remote_login(c_type, src, s_port, s_name, s_passwd, c_prompt)
    d_session = remote_login(c_type, dst, s_port, d_name, d_passwd, c_prompt)

    s_session.cmd("iptables -I INPUT -p %s -j ACCEPT" % d_protocol)
    d_session.cmd("iptables -I OUTPUT -p %s -j ACCEPT" % d_protocol)

    logging.info("Transfer data using netcat from %s to %s" % (src, dst))
    cmd = "nc"
    if d_protocol == "udp":
        cmd += " -u"
        cmd += " -w %s" % timeout
    s_session.sendline("%s -l %s < %s" % (cmd, d_port, s_path))
    d_session.sendline("echo a | %s %s %s > %s" % (cmd, src, d_port, d_path))

    if check_sum:
        if (s_session.cmd("md5sum %s" % s_path).split()[0] !=
                d_session.cmd("md5sum %s" % d_path).split()[0]):
            return False
    return True


def udp_copy_between_remotes(src, dst, s_port, s_passwd, d_passwd,
                             s_name, d_name, s_path, d_path,
                             c_type="ssh", c_prompt="\n",
                             d_port="9000", timeout=600):
    """
    Copy files from a remote host (guest) to another remote host (guest) by
    udp.

    :param src/dst: Hostname or IP address of src and dst
    :param s_name/d_name: Username (if required)
    :param s_passwd/d_passwd: Password (if required)
    :param s_path/d_path: Path on the remote machine where we are copying
    :param c_type: Login method to remote host(guest).
    :param c_prompt : command line prompt of remote host(guest)
    :param d_port:  the port data transfer
    :param timeout: data transfer timeout

    """
    s_session = remote_login(c_type, src, s_port, s_name, s_passwd, c_prompt)
    d_session = remote_login(c_type, dst, s_port, d_name, d_passwd, c_prompt)

    def get_abs_path(session, filename, extension):
        """
        return file path drive+path
        """
        cmd_tmp = "wmic datafile where \"Filename='%s' and "
        cmd_tmp += "extension='%s'\" get drive^,path"
        cmd = cmd_tmp % (filename, extension)
        info = session.cmd_output(cmd, timeout=360).strip()
        drive_path = re.search(r'(\w):\s+(\S+)', info, re.M)
        if not drive_path:
            raise error.TestError("Not found file %s.%s in your guest"
                                  % (filename, extension))
        return ":".join(drive_path.groups())

    def get_file_md5(session, file_path):
        """
        Get files md5sums
        """
        if c_type == "ssh":
            md5_cmd = "md5sum %s" % file_path
            md5_reg = r"(\w+)\s+%s.*" % file_path
        else:
            drive_path = get_abs_path(session, "md5sums", "exe")
            filename = file_path.split("\\")[-1]
            md5_reg = r"%s\s+(\w+)" % filename
            md5_cmd = '%smd5sums.exe %s | find "%s"' % (drive_path, file_path,
                                                        filename)
        o = session.cmd_output(md5_cmd)
        file_md5 = re.findall(md5_reg, o)
        if not o:
            raise error.TestError("Get file %s md5sum error" % file_path)
        return file_md5

    def server_alive(session):
        if c_type == "ssh":
            check_cmd = "ps aux"
        else:
            check_cmd = "tasklist"
        o = session.cmd_output(check_cmd)
        if not o:
            raise error.TestError("Can not get the server status")
        if "sendfile" in o.lower():
            return True
        return False

    def start_server(session):
        if c_type == "ssh":
            start_cmd = "sendfile %s &" % d_port
        else:
            drive_path = get_abs_path(session, "sendfile", "exe")
            start_cmd = "start /b %ssendfile.exe %s" % (drive_path,
                                                        d_port)
        session.cmd_output_safe(start_cmd)
        if not server_alive(session):
            raise error.TestError("Start udt server failed")

    def start_client(session):
        if c_type == "ssh":
            client_cmd = "recvfile %s %s %s %s" % (src, d_port,
                                                   s_path, d_path)
        else:
            drive_path = get_abs_path(session, "recvfile", "exe")
            client_cmd_tmp = "%srecvfile.exe %s %s %s %s"
            client_cmd = client_cmd_tmp % (drive_path, src, d_port,
                                           s_path.split("\\")[-1],
                                           d_path.split("\\")[-1])
        session.cmd_output_safe(client_cmd, timeout)

    def stop_server(session):
        if c_type == "ssh":
            stop_cmd = "killall sendfile"
        else:
            stop_cmd = "taskkill /F /IM sendfile.exe"
        if server_alive(session):
            session.cmd_output_safe(stop_cmd)

    try:
        src_md5 = get_file_md5(s_session, s_path)
        if not server_alive(s_session):
            start_server(s_session)
        start_client(d_session)
        dst_md5 = get_file_md5(d_session, d_path)
        if src_md5 != dst_md5:
            err_msg = "Files md5sum mismatch, file %s md5sum is '%s', "
            err_msg = "but the file %s md5sum is %s"
            raise error.TestError(err_msg % (s_path, src_md5,
                                             d_path, dst_md5))
    finally:
        stop_server(s_session)
        s_session.close()
        d_session.close()


def copy_files_to(address, client, username, password, port, local_path,
                  remote_path, limit="", log_filename=None,
                  verbose=False, timeout=600, interface=None):
    """
    Copy files to a remote host (guest) using the selected client.

    :param client: Type of transfer client
    :param username: Username (if required)
    :param password: Password (if requried)
    :param local_path: Path on the local machine where we are copying from
    :param remote_path: Path on the remote machine where we are copying to
    :param address: Address of remote host(guest)
    :param limit: Speed limit of file transfer.
    :param log_filename: If specified, log all output to this file (SCP only)
    :param verbose: If True, log some stats using logging.debug (RSS only)
    :param timeout: The time duration (in seconds) to wait for the transfer to
            complete.
    :interface: The interface the neighbours attach to (only use when using ipv6
                linklocal address.)
    :raise: Whatever remote_scp() raises
    """
    if client == "scp":
        scp_to_remote(address, port, username, password, local_path,
                      remote_path, limit, log_filename, timeout,
                      interface=interface)
    elif client == "rss":
        log_func = None
        if verbose:
            log_func = logging.debug
        c = rss_client.FileUploadClient(address, port, log_func)
        c.upload(local_path, remote_path, timeout)
        c.close()


def copy_files_from(address, client, username, password, port, remote_path,
                    local_path, limit="", log_filename=None,
                    verbose=False, timeout=600, interface=None):
    """
    Copy files from a remote host (guest) using the selected client.

    :param client: Type of transfer client
    :param username: Username (if required)
    :param password: Password (if requried)
    :param remote_path: Path on the remote machine where we are copying from
    :param local_path: Path on the local machine where we are copying to
    :param address: Address of remote host(guest)
    :param limit: Speed limit of file transfer.
    :param log_filename: If specified, log all output to this file (SCP only)
    :param verbose: If True, log some stats using logging.debug (RSS only)
    :param timeout: The time duration (in seconds) to wait for the transfer to
    complete.
    :interface: The interface the neighbours attach to (only use when using ipv6
                linklocal address.)
    :raise: Whatever remote_scp() raises
    """
    if client == "scp":
        scp_from_remote(address, port, username, password, remote_path,
                        local_path, limit, log_filename, timeout,
                        interface=interface)
    elif client == "rss":
        log_func = None
        if verbose:
            log_func = logging.debug
        c = rss_client.FileDownloadClient(address, port, log_func)
        c.download(remote_path, local_path, timeout)
        c.close()


class Remote_Package(object):

    def __init__(self, address, client, username, password, port, remote_path):
        """
        Initialization of Remote Package class.

        :param address: Address of remote host(guest)
        :param client: The client to use ('ssh', 'telnet' or 'nc')
        :param username: Username (if required)
        :param password: Password (if requried)
        :param port: Port to connect to
        :param remote_path: Rmote package path
        """
        self.address = address
        self.client = client
        self.port = port
        self.username = username
        self.password = password
        self.remote_path = remote_path

        if self.client == "nc":
            self.cp_client = "rss"
            self.cp_port = 10023
        elif self.client == "ssh":
            self.cp_client = "scp"
            self.cp_port = 22
        else:
            raise LoginBadClientError(client)

    def pull_file(self, local_path, timeout=600):
        """
        Copy file from remote to local.
        """
        logging.debug("Pull remote: '%s' to local: '%s'." % (self.remote_path,
                                                             local_path))
        copy_files_from(self.address, self.cp_client, self.username,
                        self.password, self.cp_port, self.remote_path,
                        local_path, timeout=timeout)

    def push_file(self, local_path, timeout=600):
        """
        Copy file from local to remote.
        """
        logging.debug("Push local: '%s' to remote: '%s'." % (local_path,
                                                             self.remote_path))
        copy_files_to(self.address, self.cp_client, self.username,
                      self.password, self.cp_port, local_path,
                      self.remote_path, timeout=timeout)


class RemoteFile(object):

    """
    Class to handle the operations of file on remote host or guest.
    """

    def __init__(self, address, client, username, password, port,
                 remote_path, limit="", log_filename=None,
                 verbose=False, timeout=600):
        """
        Initialization of RemoteFile class.

        :param address: Address of remote host(guest)
        :param client: Type of transfer client
        :param username: Username (if required)
        :param password: Password (if requried)
        :param remote_path: Path of file which we want to edit on remote.
        :param limit: Speed limit of file transfer.
        :param log_filename: If specified, log all output to this file(SCP only)
        :param verbose: If True, log some stats using logging.debug (RSS only)
        :param timeout: The time duration (in seconds) to wait for the
                        transfer tocomplete.
        """
        self.address = address
        self.client = client
        self.username = username
        self.password = password
        self.port = port
        self.remote_path = remote_path
        self.limit = limit
        self.log_filename = log_filename
        self.verbose = verbose
        self.timeout = timeout

        # Get a local_path and all actions is taken on it.
        filename = os.path.basename(self.remote_path)

        # Get a local_path.
        tmp_dir = data_dir.get_tmp_dir()
        local_file = tempfile.NamedTemporaryFile(prefix=("%s_" % filename),
                                                 dir=tmp_dir)
        self.local_path = local_file.name
        local_file.close()

        # Get a backup_path.
        backup_file = tempfile.NamedTemporaryFile(prefix=("%s_" % filename),
                                                  dir=tmp_dir)
        self.backup_path = backup_file.name
        backup_file.close()

        # Get file from remote.
        self._pull_file()
        # Save a backup.
        shutil.copy(self.local_path, self.backup_path)

    def __del__(self):
        """
        Called when the instance is about to be destroyed.
        """
        self._reset_file()
        if os.path.exists(self.backup_path):
            os.remove(self.backup_path)
        if os.path.exists(self.local_path):
            os.remove(self.local_path)

    def _pull_file(self):
        """
        Copy file from remote to local.
        """
        if self.client == "test":
            shutil.copy(self.remote_path, self.local_path)
        else:
            copy_files_from(self.address, self.client, self.username,
                            self.password, self.port, self.remote_path,
                            self.local_path, self.limit, self.log_filename,
                            self.verbose, self.timeout)

    def _push_file(self):
        """
        Copy file from local to remote.
        """
        if self.client == "test":
            shutil.copy(self.local_path, self.remote_path)
        else:
            copy_files_to(self.address, self.client, self.username,
                          self.password, self.port, self.local_path,
                          self.remote_path, self.limit, self.log_filename,
                          self.verbose, self.timeout)

    def _reset_file(self):
        """
        Copy backup from local to remote.
        """
        if self.client == "test":
            shutil.copy(self.backup_path, self.remote_path)
        else:
            copy_files_to(self.address, self.client, self.username,
                          self.password, self.port, self.backup_path,
                          self.remote_path, self.limit, self.log_filename,
                          self.verbose, self.timeout)

    def _read_local(self):
        """
        Read file on local_path.

        :return: string list got from readlines().
        """
        local_file = open(self.local_path, "r")
        lines = local_file.readlines()
        local_file.close()
        return lines

    def _write_local(self, lines):
        """
        Write file on local_path. Call writelines method of File.
        """
        local_file = open(self.local_path, "w")
        local_file.writelines(lines)
        local_file.close()

    def add(self, line_list):
        """
        Append lines in line_list into file on remote.
        """
        lines = self._read_local()
        for line in line_list:
            lines.append("\n%s" % line)
        self._write_local(lines)
        self._push_file()

    def sub(self, pattern2repl_dict):
        """
        Replace the string which match the pattern
        to the value contained in pattern2repl_dict.
        """
        lines = self._read_local()
        for pattern, repl in pattern2repl_dict.items():
            for index in range(len(lines)):
                line = lines[index]
                lines[index] = re.sub(pattern, repl, line)
        self._write_local(lines)
        self._push_file()

    def remove(self, pattern_list):
        """
        Remove the lines in remote file which matchs a pattern
        in pattern_list.
        """
        lines = self._read_local()
        for pattern in pattern_list:
            for index in range(len(lines)):
                line = lines[index]
                if re.match(pattern, line):
                    lines.remove(line)
                    # Check this line is the last one or not.
                    if (not line.endswith('\n') and (index > 0)):
                        lines[index - 1] = lines[index - 1].rstrip("\n")
        self._write_local(lines)
        self._push_file()

    def sub_else_add(self, pattern2repl_dict):
        """
        Replace the string which match the pattern.
        If no match in the all lines, append the value
        to the end of file.
        """
        lines = self._read_local()
        for pattern, repl in pattern2repl_dict.items():
            no_line_match = True
            for index in range(len(lines)):
                line = lines[index]
                if re.match(pattern, line):
                    no_line_match = False
                    lines[index] = re.sub(pattern, repl, line)
            if no_line_match:
                lines.append("\n%s" % repl)
        self._write_local(lines)
        self._push_file()


class RemoteRunner(object):

    """
    Class to provide a utils.run-like method to execute command on
    remote host or guest. Provide a similar interface with utils.run
    on local.
    """

    def __init__(self, client="ssh", host=None, port="22", username="root",
                 password=None, prompt=r"[\#\$]\s*$", linesep="\n",
                 log_filename=None, timeout=240, internal_timeout=10,
                 session=None):
        """
        Initialization of RemoteRunner. Init a session login to remote host or
        guest.

        :param client: The client to use ('ssh', 'telnet' or 'nc')
        :param host: Hostname or IP address
        :param port: Port to connect to
        :param username: Username (if required)
        :param password: Password (if required)
        :param prompt: Shell prompt (regular expression)
        :param linesep: The line separator to use when sending lines
                (e.g. '\\n' or '\\r\\n')
        :param log_filename: If specified, log all output to this file
        :param timeout: Total time duration to wait for a successful login
        :param internal_timeout: The maximal time duration (in seconds) to wait
                for each step of the login procedure (e.g. the "Are you sure"
                prompt or the password prompt)
        :param session: An existing session
        :see: wait_for_login()
        :raise: Whatever wait_for_login() raises
        """
        if session is None:
            if host is None:
                raise error.TestError("Neither host, nor session was defined!")
            self.session = wait_for_login(client, host, port, username,
                                          password, prompt, linesep,
                                          log_filename, timeout,
                                          internal_timeout)
        else:
            self.session = session
        # Init stdout pipe and stderr pipe.
        self.stdout_pipe = tempfile.mktemp()
        self.stderr_pipe = tempfile.mktemp()

    def run(self, command, timeout=60, ignore_status=False):
        """
        Method to provide a utils.run-like interface to execute command on
        remote host or guest.

        :param timeout: Total time duration to wait for command return.
        :param ignore_status: If ignore_status=True, do not raise an exception,
                              no matter what the exit code of the command is.
                              Else, raise CmdError if exit code of command is not
                              zero.
        """
        # Redirect the stdout and stderr to file, Deviding error message
        # from output, and taking off the color of output. To return the same
        # result with utils.run() function.
        command = "%s 1>%s 2>%s" % (command, self.stdout_pipe, self.stderr_pipe)
        status, _ = self.session.cmd_status_output(command, timeout=timeout)
        output = self.session.cmd_output("cat %s;rm -f %s" %
                                         (self.stdout_pipe, self.stdout_pipe))
        errput = self.session.cmd_output("cat %s;rm -f %s" %
                                         (self.stderr_pipe, self.stderr_pipe))
        cmd_result = utils.CmdResult(command=command, exit_status=status,
                                     stdout=output, stderr=errput)
        if (status and (not ignore_status)):
            raise error.CmdError(command, cmd_result)
        return cmd_result
