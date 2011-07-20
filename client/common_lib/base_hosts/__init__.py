from autotest_lib.client.common_lib import utils
import base_classes

Host = utils.import_site_class(
    __file__, "autotest_lib.client.common_lib.base_hosts.site_host", "SiteHost",
    base_classes.Host)