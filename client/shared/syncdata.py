from autotest.client.shared import utils
from autotest.client.shared.base_syncdata import SyncData
from autotest.client.shared.base_syncdata import SyncListenServer
from autotest.client.shared.base_syncdata import net_recv_object
from autotest.client.shared.base_syncdata import net_send_object

_SITE_MODULE_NAME = 'autotest.client.shared.site_syncdata'
net_send_object = utils.import_site_symbol(
    __file__, _SITE_MODULE_NAME, 'net_send_object', net_send_object)
net_recv_object = utils.import_site_symbol(
    __file__, _SITE_MODULE_NAME, 'net_recv_object', net_recv_object)
SyncListenServer = utils.import_site_symbol(
    __file__, _SITE_MODULE_NAME, 'SyncListenServer', SyncListenServer)
SyncData = utils.import_site_symbol(
    __file__, _SITE_MODULE_NAME, 'SyncData', SyncData)
