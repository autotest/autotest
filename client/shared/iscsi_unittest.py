#!/usr/bin/python
import os
import unittest

try:
    import autotest.common as common  # pylint: disable=W0611
except ImportError:
    import common  # pylint: disable=W0611

from autotest.client.shared import iscsi
from autotest.client.shared.test_utils import mock
from autotest.client import os_dep
from autotest.client.shared import utils


class iscsi_test(unittest.TestCase):

    def setup_stubs_init(self):
        os_dep.command.expect_call("iscsiadm")
        utils.system_output.expect_call("hostname").and_return("localhost")
        os_dep.command.expect_call("tgtadm")

    def setup_stubs_login(self, iscsi_obj):
        c_cmd = "dd if=/dev/zero of=/tmp/iscsitest count=1024 bs=1K"
        lg_cmd = "iscsiadm --mode node --login --targetname "
        lg_cmd += "%s" % iscsi_obj.target
        self.setup_stubs_portal_visible(iscsi_obj)
        os.path.isfile.expect_call(iscsi_obj.emulated_image).and_return(False)
        utils.system.expect_call(c_cmd)
        self.setup_stubs_export_target(iscsi_obj)
        utils.system.expect_call("service iscsid restart")
        self.setup_stubs_portal_visible(iscsi_obj, "127.0.0.1:3260,1 %s"
                                        % iscsi_obj.target)
        lg_msg = "successful"
        utils.system_output.expect_call(lg_cmd).and_return(lg_msg)

    def setup_stubs_get_device_name(self, iscsi_obj):
        s_msg = "tcp [15] 127.0.0.1:3260,1 %s" % iscsi_obj.target
        utils.system_output.expect_call("iscsiadm --mode session",
                                        ignore_status=True
                                        ).and_return(s_msg)
        detail = "Target: iqn.iscsitest\n Attached scsi disk "
        detail += "sdb State running"
        utils.system_output.expect_call("iscsiadm -m session -P 3"
                                        ).and_return(detail)

    def setup_stubs_cleanup(self, iscsi_obj, fname=""):
        s_msg = "tcp [15] 127.0.0.1:3260,1 %s" % iscsi_obj.target
        utils.system_output.expect_call("iscsiadm --mode session",
                                        ignore_status=True
                                        ).and_return(s_msg)

        out_cmd = "iscsiadm --mode node --logout -T %s" % iscsi_obj.target
        utils.system_output.expect_call(out_cmd).and_return("successful")
        os.path.isfile.expect_call(fname).and_return(False)
        s_cmd = "tgtadm --lld iscsi --mode target --op show"
        utils.system_output.expect_call(s_cmd
                                        ).and_return("Target 1: iqn.iscsitest")
        d_cmd = "tgtadm --lld iscsi --mode target --op delete"
        d_cmd += " --tid %s" % iscsi_obj.emulated_id
        utils.system.expect_call(d_cmd)

    def setup_stubs_logged_in(self, result=""):
        utils.system_output.expect_call("iscsiadm --mode session",
                                        ignore_status=True
                                        ).and_return(result)

    def setup_stubs_portal_visible(self, iscsi_obj, result=""):
        host_name = iscsi_obj.portal_ip
        v_cmd = "iscsiadm -m discovery -t sendtargets -p %s" % host_name
        utils.system_output.expect_call(v_cmd,
                                        ignore_status=True).and_return(result)

    def setup_stubs_export_target(self, iscsi_obj):
        s_cmd = "tgtadm --lld iscsi --mode target --op show"
        utils.system_output.expect_call(s_cmd).and_return("")
        utils.system_output.expect_call(s_cmd).and_return("")
        t_cmd = "tgtadm --mode target --op new --tid"
        t_cmd += " %s --lld iscsi " % iscsi_obj.emulated_id
        t_cmd += "--targetname %s" % iscsi_obj.target
        utils.system.expect_call(t_cmd)
        l_cmd = "tgtadm --lld iscsi --op bind --mode target"
        l_cmd += " --tid %s -I ALL" % iscsi_obj.emulated_id
        utils.system.expect_call(l_cmd)
        utils.system_output.expect_call(s_cmd).and_return("")
        t_cmd = "tgtadm --mode logicalunit --op new "
        t_cmd += "--tid %s --lld iscsi " % iscsi_obj.emulated_id
        t_cmd += "--lun %s " % 0
        t_cmd += "--backing-store %s" % iscsi_obj.emulated_image
        utils.system.expect_call(t_cmd)

    def setup_stubs_get_target_id(self):
        s_cmd = "tgtadm --lld iscsi --mode target --op show"
        s_msg = "Target 1: iqn.iscsitest\nBacking store path: /tmp/iscsitest"
        utils.system_output.expect_call(s_cmd).and_return(s_msg)

    def setUp(self):
        # The normal iscsi with iscsi server should configure following
        # parameters. As this will need env support only test emulated
        # iscsi in local host.
        # self.iscsi_params = {"target": "",
        #                       "portal_ip": "",
        #                       "initiator": ""}

        self.iscsi_emulated_params = {"emulated_image": "/tmp/iscsitest",
                                      "target": "iqn.iscsitest",
                                      "image_size": "1024K"}
        self.god = mock.mock_god()
        self.god.stub_function(os_dep, "command")
        self.god.stub_function(utils, "system")
        self.god.stub_function(utils, "system_output")
        self.god.stub_function(os.path, "isfile")

    def tearDown(self):
        self.god.unstub_all()

    def test_iscsi_get_device_name(self):
        self.setup_stubs_init()
        iscsi_emulated = iscsi.Iscsi(self.iscsi_emulated_params)
        iscsi_emulated.emulated_id = "1"
        self.setup_stubs_login(iscsi_emulated)
        iscsi_emulated.login()
        self.setup_stubs_get_device_name(iscsi_emulated)
        self.assertNotEqual(iscsi_emulated.get_device_name(), "")
        fname = "/etc/iscsi/initiatorname.iscsi-%s" % iscsi_emulated.id
        self.setup_stubs_cleanup(iscsi_emulated, fname=fname)
        iscsi_emulated.cleanup()
        self.god.check_playback()

    def test_iscsi_login(self):
        self.setup_stubs_init()
        iscsi_emulated = iscsi.Iscsi(self.iscsi_emulated_params)
        self.setup_stubs_logged_in()
        self.assertFalse(iscsi_emulated.logged_in())
        result = "tcp [15] 127.0.0.1:3260,1 %s" % iscsi_emulated.target
        self.setup_stubs_logged_in(result)
        self.assertTrue(iscsi_emulated.logged_in())

    def test_iscsi_visible(self):
        self.setup_stubs_init()
        iscsi_emulated = iscsi.Iscsi(self.iscsi_emulated_params)
        self.setup_stubs_portal_visible(iscsi_emulated)
        self.assertFalse(iscsi_emulated.portal_visible())
        self.setup_stubs_portal_visible(iscsi_emulated, "127.0.0.1:3260,1 %s"
                                        % iscsi_emulated.target)

    def test_iscsi_target_id(self):
        self.setup_stubs_init()
        iscsi_emulated = iscsi.Iscsi(self.iscsi_emulated_params)
        self.setup_stubs_get_target_id()
        self.assertNotEqual(iscsi_emulated.get_target_id(), "")


if __name__ == "__main__":
    unittest.main()
