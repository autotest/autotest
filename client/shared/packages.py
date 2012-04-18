from autotest.client.shared import utils, base_packages


SitePackageManager = utils.import_site_class(
    __file__, "autotest.client.shared.site_packages",
    "SitePackageManager", base_packages.BasePackageManager)


class PackageManager(SitePackageManager):
    pass
