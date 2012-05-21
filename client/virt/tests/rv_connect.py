"""
rv_connect.py - connect with remote-viewer to remote target

Requires: binaries remote-viewer, Xorg, netstat
          Use example kickstart RHEL-6-spice.ks

"""
import logging, os, time
from autotest.client.virt.aexpect import ShellCmdError
from autotest.client.virt import virt_utils

class RVConnectError(Exception):
    """Exception raised in case that remote-viewer fails to connect"""
    pass

def send_ticket(client_vm, ticket):
    """
    sends spice_password trough vm.sendkey()
    @param client_session - vm() object
    @param ticket - use params.get("spice_password")
    """
    logging.info("Passing ticket '%s' to the remote-viewer.", ticket)
    for character in ticket:
        client_vm.send_key(character)

    client_vm.send_key("kp_enter") # send enter

def wait_timeout(timeout=10):
    """
    time.sleep(timeout) + logging.debug(timeout)
    @param timeout=30
    """
    logging.debug("Waiting (timeout=%ss)", timeout)
    time.sleep(timeout)

def verify_established(client_session, host, port, rv_binary):
    """
    Parses netstat output for established connection on host:port
    @param client_session - vm.wait_for_login()
    @param host - host ip addr
    @param port - port for client to connect
    @param rv_binary - remote-viewer binary
    """
    rv_binary = rv_binary.split(os.path.sep)[-1]

    # !!! -n means do not resolve port names
    cmd = '(netstat -pn 2>&1| grep "^tcp.*:.*%s:%s.*ESTABLISHED.*%s.*")' % \
        (host, str(port), rv_binary)
    try:
        netstat_out = client_session.cmd(cmd)
        logging.info("netstat output: %s", netstat_out)

    except ShellCmdError:
        logging.error("Failed to get established connection from netstat")
        raise RVConnectError()

    else:
        logging.info("%s connection to %s:%s successful.",
               rv_binary, host, port)

def print_rv_version(client_session, rv_binary):
    """
    prints remote-viewer and spice-gtk version available inside client_session
    @param client_session - vm.wait_for_login()
    @param rv_binary - remote-viewer binary
    """
    logging.info("remote-viewer version: %s",
            client_session.cmd(rv_binary + " -V"))
    logging.info("spice-gtk version: %s",
            client_session.cmd(rv_binary + " --spice-gtk-version"))

def launch_gnome_session(client_session):
    """
    Launches gnome session inside client_session
    @param client_session - vm.wait_fo_login()

    metacity ensures that newly raised window will be active
    (remote-viewer auth dialog)
    which is not done by default in pure Xorg
    """
    cmd = "nohup gnome-session --display=:0.0 &> /dev/null &"
    return client_session.cmd(cmd)

def launch_xorg(client_session):
    """
    Launches Xorg inside client_session on background
    @param client_session - vm.wait_for_login()
    @param kill - killall Xorg before launch
    """
    cmd = "Xorg"
    killall(client_session, cmd)
    wait_timeout() # Wait for Xorg to exit
    cmd = "nohup " + cmd + " &> /dev/null &"
    return client_session.cmd(cmd)

def killall(client_session, pth):
    """
    calls killall execname
    @params client_session
    @params pth - path or execname
    """
    execname = pth.split(os.path.sep)[-1]
    client_session.cmd("killall %s &> /dev/null" % execname, ok_status=[0, 1])

def launch_rv(client_vm, guest_vm, params):
    """
    Launches rv_binary with args based on spice configuration
    inside client_session on background.
    remote-viewer will try to connect from vm1 from vm2

    @param client_vm - vm object
    @param guest_vm - vm object
    @param params
    """
    rv_binary = params.get("rv_binary", "remote-viewer")
    host_ip = virt_utils.get_ip_address_by_interface(params.get("bridge"))
    host_port = None
    display = params.get("display")
    cmd = rv_binary + " --display=:0.0"
    ticket = None

    client_session = client_vm.wait_for_login(
            timeout=int(params.get("login_timeout", 360)))

    if display == "spice":
        ticket = guest_vm.get_spice_var("spice_password")

        if guest_vm.get_spice_var("spice_ssl") == "yes":
            host_port = guest_vm.get_spice_var("spice_tls_port")
            cacert = "%s/%s" % (guest_vm.get_spice_var("spice_x509_prefix"),
                               guest_vm.get_spice_var("spice_x509_cacert_file"))
            #cacert subj is in format for create certificate(with '/' delimiter)
            #remote-viewer needs ',' delimiter. And also is needed to remove 
            #first character (it's '/')
            host_subj = guest_vm.get_spice_var("spice_x509_server_subj")
            host_subj = host_subj.replace('/',',')[1:]
            
            cmd += " spice://%s?tls-port=%s" % (host_ip, host_port)
            cmd += " --spice-ca-file=%s" % cacert
            
            if params.get("spice_client_host_subject") == "yes":
                cmd += " --spice-host-subject=\"%s\"" % host_subj
    
            #client needs cacert file
            client_session.cmd("rm -rf %s && mkdir -p %s" % (
                               guest_vm.get_spice_var("spice_x509_prefix"),
                               guest_vm.get_spice_var("spice_x509_prefix")))
            virt_utils.copy_files_to(client_vm.get_address(), 'scp', 
                                     params.get("username"), 
                                     params.get("password"),
                                     params.get("shell_port"),
                                     cacert, cacert)
        else:
            host_port = guest_vm.get_spice_var("spice_port")
            cmd += " spice://%s?port=%s" % (host_ip, host_port)

    elif display == "vnc":
        raise NotImplementedError("remote-viewer vnc")

    else:
        raise Exception("Unsupported display value")
    cmd = "nohup " + cmd + " &> /dev/null &" # Launch it on background

    # Launching the actual set of commands
    launch_xorg(client_session)
    wait_timeout() # Wait for Xorg to start up
    launch_gnome_session(client_session)
    wait_timeout() # Wait till gnome-session starts up

    print_rv_version(client_session, rv_binary)

    logging.info("Launching %s on the client (virtual)", cmd)
    client_session.cmd(cmd)

    # client waits for user entry (authentication) if spice_password is set
    if ticket:
        wait_timeout() # Wait for remote-viewer to launch
        send_ticket(client_vm, ticket)

    wait_timeout() # Wait for conncetion to establish
    verify_established(client_session, host_ip, host_port, rv_binary)



def run_rv_connect(test, params, env):
    """
    Simple test for Remote Desktop connection
    Tests expectes that Remote Desktop client (spice/vnc) will be executed
    from within a second guest so we won't be limited to Linux only clients

    The plan is to support remote-viewer at first place

    @param test: KVM test object.  @param params: Dictionary with the test parameters.
    @param env: Dictionary with test environment.
    """

    guest_vm = env.get_vm(params["guest_vm"])
    guest_vm.verify_alive()
    guest_session = guest_vm.wait_for_login(
            timeout=int(params.get("login_timeout", 360)))

    client_vm = env.get_vm(params["client_vm"])
    client_vm.verify_alive()
    client_session = client_vm.wait_for_login(
            timeout=int(params.get("login_timeout", 360)))

    launch_rv(client_vm, guest_vm, params)

    client_session.close()
    guest_session.close()
