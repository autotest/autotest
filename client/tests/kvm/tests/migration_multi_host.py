import logging, socket
from autotest_lib.client.common_lib import error


def run_migration_multi_host(test, params, env):
    """
    KVM multi-host migration test:

    Migration execution progress:

    source host                       dest host
    ----------------------------------------------------------------------------
    log into guest
    ----------------------------------------------------------------------------
    start socket server

    wait 30 secs -------------------- wait login_timeout+30 secs ---------------

    accept connection                 connect to socket server,send mig_port
    ----------------------------------------------------------------------------
    start migration

    wait 30 secs -------------------- wait mig_timeout+30 secs -----------------

    try to log into migrated guest    check VM's status via monitor cmd
    ----------------------------------------------------------------------------

    @param test: kvm test object.
    @param params: Dictionary with test parameters.
    @param env: Dictionary with the test environment.
    """
    def guest_active(vm):
        o = vm.monitor.info("status")
        if isinstance(o, str):
            return "status: running" in o
        else:
            return o.get("status") == "running"

    vm = env.get_vm(params["main_vm"])
    vm.verify_alive()
    login_timeout = int(params.get("login_timeout", 360))
    role = params.get("role")
    srchost = params.get("srchost")
    dsthost = params.get("dsthost")
    mig_timeout = int(params.get("mig_timeout"))
    # Port used to communicate info between source and destination
    comm_port = int(params.get("comm_port", 12324))
    regain_ip_cmd = params.get("regain_ip_cmd", "dhclient")
    if role == 'source':
        session = vm.wait_for_login(timeout=login_timeout)

        # Listen on a port to get the migration port received from
        # dest machine
        s_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s_socket.bind(('', comm_port))
        s_socket.listen(1)

        # Wait 30 seconds for source and dest to reach this point
        test.job.barrier(srchost, 'socket_started', 30).rendezvous(srchost,
                                                                   dsthost)

        c_socket = s_socket.accept()[0]
        mig_port = int(c_socket.recv(6))
        logging.info("Received from destination the migration port %s",
                     mig_port)
        c_socket.close()

        logging.info("Start migrating now...")
        vm.migrate(dest_host=dsthost, remote_port=mig_port)

        # Wait up to 30 seconds for dest to reach this point
        test.job.barrier(srchost, 'mig_finished', 30).rendezvous(srchost,
                                                                 dsthost)

    elif role == 'destination':
        # Wait up to login_timeout + 30 seconds for the source to
        # reach this point
        test.job.barrier(dsthost, 'socket_started',
                         login_timeout + 30).rendezvous(srchost,
                                                        dsthost)

        c_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        c_socket.connect((srchost, comm_port))
        logging.info("Communicating to source migration port %s",
                     vm.migration_port)
        c_socket.send("%d" % vm.migration_port)
        c_socket.close()

        # Wait up to mig_timeout + 30 seconds for the source to
        # reach this point: migration finished
        test.job.barrier(dsthost, 'mig_finished',
                         mig_timeout + 30).rendezvous(srchost,
                                                      dsthost)

        if not guest_active(vm):
            raise error.TestFail("Guest not active after migration")

        logging.info("Migrated guest appears to be running")

        # Log into the guest again
        logging.info("Logging into migrated guest after migration...")
        session_serial = vm.wait_for_serial_login(timeout=login_timeout)
        session_serial.cmd(regain_ip_cmd)
        session = vm.wait_for_login(timeout=login_timeout)

    else:
        raise error.TestError('Invalid role specified')
