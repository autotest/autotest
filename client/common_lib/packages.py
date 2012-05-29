from autotest_lib.client.common_lib import utils, base_packages


SitePackageManager = utils.import_site_class(
    __file__, "autotest_lib.client.common_lib.site_packages",
    "SitePackageManager", base_packages.BasePackageManager)


class PackageManager(SitePackageManager):
    pass
