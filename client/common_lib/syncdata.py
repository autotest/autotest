from autotest_lib.client.common_lib.base_syncdata import SyncData
from autotest_lib.client.common_lib.base_syncdata import SyncListenServer
from autotest_lib.client.common_lib.base_syncdata import net_send_object
from autotest_lib.client.common_lib.base_syncdata import net_recv_object
from autotest_lib.client.common_lib import utils

_SITE_MODULE_NAME = 'autotest_lib.client.common_lib.site_syncdata'
net_send_object = utils.import_site_symbol(
        __file__, _SITE_MODULE_NAME, 'net_send_object', net_send_object)
net_recv_object = utils.import_site_symbol(
        __file__, _SITE_MODULE_NAME, 'net_recv_object', net_recv_object)
SyncListenServer = utils.import_site_symbol(
        __file__, _SITE_MODULE_NAME, 'SyncListenServer', SyncListenServer)
SyncData = utils.import_site_symbol(
        __file__, _SITE_MODULE_NAME, 'SyncData', SyncData)
