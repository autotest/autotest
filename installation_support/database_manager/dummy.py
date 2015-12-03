"""
Dummy implementation of the database manager interface
"""

from autotest.installation_support.database_manager import base


class DummyDatabaseManager(base.BaseDatabaseManager):

    '''
    Dummy class that manages no database
    '''

    def exists(self):
        '''
        Checks if the database instance exists
        '''
        return False

    def admin_credentials_valid(self):
        '''
        Checks if the admin user credentials are valid system wide

        What this means is that we won't try to connect to a specific database
        instance, but to the RDBMS as a whole (where appropriate)
        '''
        return True

    def create_instance(self):
        '''
        Creates the database instance
        '''
        return True

    def grant_privileges(self):
        return True

    def setup(self):
        '''
        Performs all the steps neede to completely setup a database instance
        '''
        return True

    def run_sql(self, sql):
        '''
        Runs the given SQL code blindly
        '''
        return True
