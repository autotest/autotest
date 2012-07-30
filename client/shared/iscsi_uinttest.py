import unittest

try:
    import autotest.common as common
except ImportError:
    import common

from autotest.client.shared import iscsi

class iscsi_test(unittest.TestCase):

    def setUp(self):
        # The normal iscsi with iscsi server should configure following
        # parameters. As this will need env support only test emulated
        # iscsi in local host.
        # self.iscsi_params = {"target": "",
        #                       "portal_ip": "",
        #                       "initiator": ""}

        self.iscsi_emulated_params = {"emulated_image": "/tmp/iscsitest",
                                     "target": "iqn.iscsitest",
                                     "image_size": "1024"}


    def test_iscsi_get_device_name(self):
        iscsi_emulated = iscsi.Iscsi(self.iscsi_emulated_params)
        iscsi_emulated.login()
        self.assertNotEqual(iscsi_emulated.get_device_name(), "")
        iscsi_emulate.cleanup()


    def test_iscsi_login(self):
        iscsi_emulated = iscsi.Iscsi(self.iscsi_emulated_params)
        self.assertFalse(iscsi_emulated.is_login())
        iscsi_emulated.login()
        self.assertTrue(iscsi_emulated.is_login())
        iscsi_emulated.cleanup()


    def test_iscsi_visible(self):
        iscsi_emulated = iscsi.Iscsi(self.iscsi_emulated_params)
        self.assertFalse(iscsi_emulated.is_visible())
        iscsi_emulated.export_target()
        self.assertTrue(iscsi_emulated.is_visible())
        iscsi_emulated.cleanup()


    def test_iscsi_target_id(self):
        iscsi_emulated = iscsi.Iscsi(self.iscsi_emulated_params)
        iscsi_emulated.export_target()
        self.assertNotEqual(iscsi_emulated.get_target_id(), "")
        iscsi_emulated.cleanup()


if __name__ == "__main__":
    unittest.main()
