from autotest_lib.client.common_lib.base_barrier import listen_server, barrier
from autotest_lib.client.common_lib import utils

_SITE_MODULE_NAME = 'autotest_lib.client.common_lib.site_barrier'
listen_server = utils.import_site_symbol(
        __file__, _SITE_MODULE_NAME, 'listen_server', listen_server)
barrier = utils.import_site_symbol(
        __file__, _SITE_MODULE_NAME, 'barrier', barrier)
