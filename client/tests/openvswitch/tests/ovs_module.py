import os, logging
from virttest import utils_misc
from autotest.client.shared import openvswitch, error, utils


@error.context_aware
def run_ovs_module(test, params, env):
    """
    Run basic test of OpenVSwitch driver.
    """
    ovs = None
    try:
        try:
            error.context("Remove all bridge from OpenVSwitch.")
            ovs = openvswitch.OpenVSwitch(test.tmpdir)
            ovs.init_system()
            ovs.check()
            for br in ovs.list_br():
                ovs.del_br(br)

            ovs.clean()

            for _ in range(int(params.get("mod_loaditer", 100))):
                utils.run("modprobe openvswitch")
                utils.run("rmmod openvswitch")

        except Exception, e:
            logging.error("Test failed: %s: %s",
                          e.__class__.__name__, e)
            raise
    finally:
        try:
            if ovs:
                if ovs.cleanup:
                    ovs.clean()
        except Exception:
            raise
