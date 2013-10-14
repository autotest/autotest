"""
Install server interfaces, for autotest client machine OS provisioning.
"""
import os
import xmlrpclib
import logging
import time
from autotest.client.shared import error


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

        :param **kwargs: Dict of keyword arguments passed to constructor.
        """
        self.xmlrpc_url = kwargs['xmlrpc_url']
        self.user = kwargs['user']
        self.password = kwargs['password']
        self.fallback_profile = kwargs['fallback_profile']
        if self.xmlrpc_url:
            self.server = xmlrpclib.Server(self.xmlrpc_url)
            self.token = self.server.login(self.user, self.password)
        self.num_attempts = int(kwargs.get('num_attempts', 2))

    def get_system_handle(self, host):
        """
        Get a system handle, needed to perform operations on the given host

        :param host: Host name

        :return: Tuple (system, system_handle)
        """
        try:
            system = self.server.find_system({"name": host.hostname})[0]
        except IndexError, detail:
            # TODO: Method to register this system as brand new
            logging.error("Error finding %s: %s", host.hostname, detail)
            raise ValueError("No system %s registered on install server" %
                             host.hostname)

        system_handle = self.server.get_system_handle(system, self.token)
        return (system, system_handle)

    def _set_host_profile(self, host, profile=''):
        system, system_handle = self.get_system_handle(host)
        system_info = self.server.get_system(system)

        # If no fallback profile is enabled, we don't want to mess
        # with the currently profile set for that machine.
        if profile:
            self.server.modify_system(system_handle, 'profile', profile,
                                      self.token)
            self.server.save_system(system_handle, self.token)

        # Enable netboot for that machine (next time it'll reboot and be
        # reinstalled)
        self.server.modify_system(system_handle, 'netboot_enabled', 'True',
                                  self.token)
        self.server.save_system(system_handle, self.token)
        try:
            # Cobbler only generates the DHCP configuration for netboot enabled
            # machines, so we need to synchronize the dhcpd file after changing
            # the value above
            self.server.sync_dhcp(self.token)
        except xmlrpclib.Fault, err:
            # older Cobbler will not recognize the above command
            if not "unknown remote method" in err.faultString:
                logging.error("DHCP sync failed, error code: %s, error string: %s",
                              err.faultCode, err.faultString)

    def install_host(self, host, profile='', timeout=None, num_attempts=2):
        """
        Install a host object with profile name defined by distro.

        :param host: Autotest host object.
        :param profile: String with cobbler profile name.
        :param timeout: Amount of time to wait for the install.
        :param num_attempts: Maximum number of install attempts.
        """
        if not self.xmlrpc_url:
            return

        installations_attempted = 1

        step_time = 60
        if timeout is None:
            # 1 hour of timeout by default
            timeout = 3600

        system, system_handle = self.get_system_handle(host)
        if not profile:
            profile = self.server.get_system(system).get('profile')
        if not profile:
            e_msg = 'Unable to determine profile for host %s' % host.hostname
            raise error.HostInstallProfileError(e_msg)

        host.record("START", None, "install", host.hostname)
        host.record("GOOD", None, "install.start", host.hostname)
        logging.info("Installing machine %s with profile %s (timeout %s s)",
                     host.hostname, profile, timeout)
        install_start = time.time()
        time_elapsed = 0

        install_successful = False
        while ((not install_successful) and
               (installations_attempted <= self.num_attempts) and
               (time_elapsed < timeout)):

            self._set_host_profile(host, profile)
            self.server.power_system(system_handle,
                                     'reboot', self.token)
            installations_attempted += 1

            while time_elapsed < timeout:

                time.sleep(step_time)

                # Cobbler signals that installation if finished by running
                # a %post script that unsets netboot_enabled. So, if it's
                # still set, installation has not finished. Loop and sleep.
                if not self.server.get_system(system).get('netboot_enabled'):
                    logging.debug('Cobbler got signaled that host %s '
                                  'installation is finished',
                                  host.hostname)
                    break

            # Check if the installed profile matches what we asked for
            installed_profile = self.server.get_system(system).get('profile')
            install_successful = (installed_profile == profile)

            if install_successful:
                logging.debug('Host %s installation successful', host.hostname)
                break
            else:
                logging.info('Host %s installation resulted in different '
                             'profile', host.hostname)

            time_elapsed = time.time() - install_start

        if not install_successful:
            e_msg = 'Host %s install timed out' % host.hostname
            host.record("END FAIL", None, "install", e_msg)
            raise error.HostInstallTimeoutError(e_msg)

        remove_hosts_file()
        host.wait_for_restart()
        host.record("END GOOD", None, "install", host.hostname)
        time_elapsed = time.time() - install_start
        logging.info("Machine %s installed successfully after %d s (%d min)",
                     host.hostname, time_elapsed, time_elapsed / 60)

    def power_host(self, host, state='reboot'):
        """
        Power on/off/reboot a host through cobbler.

        :param host: Autotest host object.
        :param state: Allowed states - one of 'on', 'off', 'reboot'.
        """
        if self.xmlrpc_url:
            system_handle = self.get_system_handle(host)[1]
            self.server.power_system(system_handle, state, self.token)
