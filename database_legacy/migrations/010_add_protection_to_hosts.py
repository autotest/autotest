from autotest.client.shared import host_protections
from autotest.client.shared.settings import settings


def migrate_up(manager):
    manager.execute_script(ADD_PROTECTION_COLUMN)


def migrate_down(manager):
    manager.execute(DROP_COLUMN)


default_protection = settings.get_value('HOSTS', 'default_protection')
default_protection_value = host_protections.Protection.get_value(
    default_protection)

ADD_PROTECTION_COLUMN = """ALTER TABLE hosts
                           ADD COLUMN protection INT NOT NULL
                           DEFAULT %s;

                           ALTER TABLE hosts
                           ALTER COLUMN protection
                           DROP DEFAULT;
                           """ % default_protection_value

DROP_COLUMN = """ALTER TABLE hosts
                 DROP COLUMN protection"""
