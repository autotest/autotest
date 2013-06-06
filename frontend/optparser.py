"""
Default command line option parser for applications that use the frontend
functionality, that is, direct database access via frontend models.
"""

import optparse


# pylint: disable=I0011,R0904
class OptionParser(optparse.OptionParser):
    '''
    Command line option parser for app that wrap frontend functionality
    '''
    def __init__(self, usage=""):
        optparse.OptionParser.__init__(self, usage=usage)

        database = optparse.OptionGroup(self, 'DATABASE ACCESS')
        database.add_option("-s", "--database-hostname", metavar="HOSTNAME",
                            help="Database server hostname")
        database.add_option("-u", "--database-username", metavar="USERNAME",
                            help="Database username")
        database.add_option("-p", "--database-password", metavar="PASSWORD",
                            help="Database password")
        database.add_option("-d", "--database-name", metavar="NAME",
                            help="Database name")
        self.add_option_group(database)
