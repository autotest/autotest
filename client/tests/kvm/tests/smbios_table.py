import commands, logging
from autotest_lib.client.common_lib import utils, error
from autotest_lib.client.virt import virt_env_process, virt_test_utils


@error.context_aware
def run_smbios_table(test, params, env):
    """
    Check smbios table :
    1) Boot a guest with smbios options
    2) verify if host bios options have been emulated

    @param test: KVM test object.
    @param params: Dictionary with the test parameters.
    @param env: Dictionary with test environment.
    """
    vendor_cmd = "dmidecode --type 0 | grep Vendor | awk '{print $2}'"
    date_cmd = "dmidecode --type 0 | grep Date | awk '{print $3}'"
    version_cmd = "dmidecode --type 0 | grep Version | awk '{print $2}'"

    error.context("getting smbios table on host")
    host_vendor = utils.system_output(vendor_cmd)
    host_date = utils.system_output(date_cmd)
    host_version = utils.system_output(version_cmd)

    smbios = (" -smbios type=0,vendor=%s,version=%s,date=%s" %
              (host_vendor, host_version, host_date))

    extra_params = params.get("extra_params", "")
    params["extra_params"] = extra_params + smbios

    logging.debug("Booting guest %s", params.get("main_vm"))
    virt_env_process.preprocess_vm(test, params, env, params.get("main_vm"))
    vm = env.get_vm(params["main_vm"])
    vm.create()
    login_timeout = float(params.get("login_timeout", 360))
    session = vm.wait_for_login(timeout=login_timeout)

    error.context("getting smbios table on guest")
    guest_vendor = session.cmd(vendor_cmd).strip()
    guest_date = session.cmd(date_cmd).strip()
    guest_version = session.cmd(version_cmd).strip()

    failures = []

    if host_vendor != guest_vendor:
        e_msg = ("Vendor str mismatch -> host: %s guest: %s" %
                 (guest_vendor, host_vendor))
        logging.error(e_msg)
        failures.append(e_msg)

    if host_date != guest_date:
        e_msg = ("Date str mismatch -> host: %s guest: %s" %
                 (guest_date, host_date))
        logging.error(e_msg)
        failures.append(e_msg)

    if host_version != guest_version:
        e_msg = ("Version str mismatch -> host: %s guest: %s" %
                 (guest_version, host_version))
        logging.error(e_msg)
        failures.append(e_msg)

    error.context("")
    if failures:
        raise error.TestFail("smbios table test reported %s failures:\n%s" %
                             (len(failures), "\n".join(failures)))
