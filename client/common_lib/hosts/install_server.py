"""
Install server interfaces, for autotest client machine OS provisioning.
"""
import os, xmlrpclib, logging, time
from autotest_lib.client.common_lib import error


def remove_hosts_file():
    """
    Remove the ssh known hosts file for a machine.

    Sometimes it is useful to have this done since on a test lab, SSH
    fingerprints of the test machines keep changing all the time due
    to frequent reinstalls.
    """
    known_hosts_file = "%s/.ssh/known_hosts" % os.getenv("HOME")
    if os.path.isfile(known_hosts_file):
        logging.debug("Deleting known hosts file %s", known_hosts_file)
        os.remove(known_hosts_file)


class CobblerInterface(object):
    """
    Implements interfacing with the Cobbler install server.

    @see: https://fedorahosted.org/cobbler/
    """
    def __init__(self, **kwargs):
        """
        Sets class attributes from the keyword arguments passed to constructor.

        @param **kwargs: Dict of keyword arguments passed to constructor.
        """
        self.xmlrpc_url = kwargs['xmlrpc_url']
        self.user = kwargs['user']
        self.password = kwargs['password']


    def install_host(self, host, profile=None, timeout=None):
        """
        Install a host object with profile name defined by distro.

        @param host: Autotest host object.
        @param profile: String with cobbler profile name.
        @param timeout: Amount of time to wait for the install.
        """
        if self.xmlrpc_url:

            step_time = 60
            if timeout is None:
                # 1 hour of timeout by default
                timeout = 1 * 3600

            logging.info("Setting up machine %s install", host.hostname)
            remove_hosts_file()
            server = xmlrpclib.Server(self.xmlrpc_url)
            token = server.login(self.user, self.password)

            try:
                system = server.find_system({"name" : host.hostname})[0]
            except IndexError, detail:
                ### TODO: Method to register this system as brand new
                logging.error("Error finding %s: %s", host.hostname, detail)
                raise ValueError("No system %s registered on install server" %
                                 host.hostname)

            system_handle = server.get_system_handle(system, token)
            if profile is not None:
                server.modify_system(system_handle, 'profile', profile, token)
            else:
                system_info = server.get_system(system)
                profile = '%s (default)' % system_info.get('profile')
            # Enable netboot for that machine (next time it'll reboot and be
            # reinstalled)
            server.modify_system(system_handle, 'netboot_enabled', 'True', token)
            # Now, let's just restart the machine (machine has to have
            # power management data properly set up).
            server.save_system(system_handle, token)
            server.power_system(system_handle, 'reboot', token)
            logging.info("Installing machine %s with profile %s (timeout %s s)",
                         host.hostname, profile, timeout)
            install_start = time.time()
            time_elapsed = 0
            install_successful = False
            while time_elapsed < timeout:
                time.sleep(step_time)
                system_info = server.get_system(system)
                install_successful = not system_info.get('netboot_enabled')
                if install_successful:
                    break
                time_elapsed = time.time() - install_start

            if not install_successful:
                raise error.HostInstallTimeoutError('Machine %s install '
                                                    'timed out' % host.hostname)

            host.wait_for_restart()
            time_elapsed = time.time() - install_start
            logging.info("Machine %s installed successfuly after %d s (%d min)",
                         host.hostname, time_elapsed, time_elapsed/60)
