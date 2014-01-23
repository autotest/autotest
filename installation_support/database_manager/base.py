"""
Abstraction layer for managing different database systems

This is not a reinvention or reimplementation of Python's DB API, but a simple
API for for creating, populating and removing instances transparently.

This module implements the base interface that database specific modules should
implement.
"""


import os


class BaseDatabaseManager(object):

    '''
    Base class for mananging database instances

    Different RDMS have different ways of crearing instances, checking for
    their existence, etc.
    '''

    def __init__(self, name, admin=None, admin_password=None, user=None,
                 password=None, host=None):
        '''
        Creates a new instance
        '''
        self.name = name

        self.admin = admin

        if admin_password is None:
            self.admin_password = ''
        else:
            self.admin_password = admin_password

        if user is not None:
            self.user = user
        else:
            self.user = self.admin

        if password is not None:
            self.password = password
        else:
            self.password = admin_password

        self.host = host

    def run_sql(self, sql):
        '''
        Runs the given SQL code blindly
        '''
        return NotImplementedError

    def config_as_dict(self):
        '''
        Returns relevant database configuration as a dictionary
        '''
        return {'name': self.name,
                'admin': self.admin,
                'admin_password': self.admin_password,
                'user': self.user,
                'password': self.password,
                'host': self.host}

    def exists(self):
        '''
        Checks if the database instance exists
        '''
        raise NotImplementedError

    def admin_credentials_valid(self):
        '''
        Checks if the admin user credentials are valid system wide

        What this means is that we won't try to connect to a specific database
        instance, but to the RDBMS as a whole (where appropriate)
        '''
        raise NotImplementedError

    def create_instance(self):
        '''
        Creates the database instance
        '''
        raise NotImplementedError

    def grant_privileges(self):
        '''
        Grants necessary privileges to the database user
        '''
        return True

    def setup(self):
        '''
        Performs all the steps neede to completely setup a database instance
        '''
        raise NotImplementedError


    def create_views(self):
        '''
        Create views that are not created by default

        South does not run the initial SQL file. This could be added as an
        extension to Django's management commands but let's KISS

        :returns: True if all view commands were executed successfully, False
                  otherwise
        '''
        this_path = os.path.dirname(os.path.abspath(__file__))
        top_path = os.path.dirname(os.path.dirname(this_path))

        sql_files = ['tko-test-view.sql', 'tko-test-view-2.sql']
        for sql in sql_files:
            full_path = os.path.join(top_path, 'frontend', 'tko', 'sql', sql)
            if not os.path.exists(full_path):
                return False

            query = open(full_path).read()
            if not (self.run_sql(query)):
                return False

        return True
