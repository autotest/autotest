"""
Default command line option parser for applications that use the frontend
functionality, that is, direct database access via frontend models.
"""

import optparse

import django.conf
from autotest.client.shared import settings


def get_config_db_value(key):
    '''
    Return the value from the default autotest database config section
    '''
    return settings.settings.get_value('AUTOTEST_WEB', key)


# pylint: disable=I0011,R0904
class OptionParser(optparse.OptionParser):

    '''
    Command line option parser for app that wrap frontend functionality
    '''

    def __init__(self, usage=""):
        optparse.OptionParser.__init__(self, usage=usage)

        database = optparse.OptionGroup(self, 'DATABASE ACCESS')
        database.add_option("-s", "--database-hostname", metavar="HOSTNAME",
                            default=get_config_db_value('host'),
                            help="Database server hostname")
        database.add_option("-u", "--database-username", metavar="USERNAME",
                            default=get_config_db_value('user'),
                            help="Database username")
        database.add_option("-p", "--database-password", metavar="PASSWORD",
                            default=get_config_db_value('password'),
                            help="Database password")
        database.add_option("-d", "--database-name", metavar="NAME",
                            default=get_config_db_value('database'),
                            help="Database name")
        self.add_option_group(database)

    def parse_args(self):
        opts, args = optparse.OptionParser.parse_args(self)

        getattr(django.conf.settings, 'DATABASES')
        default_db = django.conf.settings.DATABASES['default']
        default_db['USER'] = opts.database_username
        default_db['PASSWORD'] = opts.database_password
        default_db['NAME'] = opts.database_name
        default_db['HOST'] = opts.database_hostname

        return opts, args
