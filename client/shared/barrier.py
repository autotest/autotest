from autotest.client.shared import utils
from autotest.client.shared.base_barrier import listen_server, barrier

_SITE_MODULE_NAME = 'autotest.client.shared.site_barrier'
listen_server = utils.import_site_symbol(
    __file__, _SITE_MODULE_NAME, 'listen_server', listen_server)
barrier = utils.import_site_symbol(
    __file__, _SITE_MODULE_NAME, 'barrier', barrier)
