"""
MySQL implementation of the database manager interface
"""

import logging

import MySQLdb
from autotest.installation_support.database_manager import base


class MySQLDatabaseManager(base.BaseDatabaseManager):

    '''
    Class that manages MySQL database instances
    '''

    def __init__(self, name, admin=None, admin_password=None, user=None,
                 password=None, host=None):
        '''
        Creates a new instance
        '''
        super(MySQLDatabaseManager, self).__init__(name, admin, admin_password,
                                                   user, password, host)

        if self.admin_credentials_valid():
            self.admin_connection = MySQLdb.connect(host=self.host,
                                                    user=self.admin,
                                                    passwd=self.admin_password)
        else:
            self.admin_connection = None
            logging.error("Failed to logon as the database admin user")

    def run_sql(self, sql):
        '''
        Runs the given SQL code blindly
        '''
        self.admin_connection.select_db(self.name)
        cursor = self.admin_connection.cursor()
        try:
            cursor.execute(sql)
        except (MySQLdb.ProgrammingError, MySQLdb.OperationalError):
            self.admin_connection.rollback()
            return False

        return True

    def exists(self):
        '''
        Checks if the database instance exists
        '''
        try:
            MySQLdb.connect(user=self.admin,
                            passwd=self.admin_password,
                            db=self.name,
                            host=self.host)
            return True
        except MySQLdb.OperationalError:
            return False

    def admin_credentials_valid(self):
        '''
        Checks if the admin user credentials are valid system wide

        What this means is that we won't try to connect to a specific database
        instance, but to the RDBMS as a whole (where appropriate)
        '''
        try:
            MySQLdb.connect(host=self.host,
                            user=self.admin,
                            passwd=self.admin_password)
            return True
        except MySQLdb.OperationalError:
            return False

    def create_instance(self):
        '''
        Creates the database instance
        '''
        if self.admin_connection is None:
            return False

        if self.exists():
            logging.info("Database already exists, doing nothing")
            return True

        cursor = self.admin_connection.cursor()
        try:
            cursor.execute("CREATE DATABASE %s" % self.name)
        except (MySQLdb.ProgrammingError, MySQLdb.OperationalError):
            self.admin_connection.rollback()
            return False

        return True

    def grant_privileges(self):
        '''
        Attempts to create database AND users AND set privileges
        '''
        grant_cmds = ["grant all privileges on %(name)s.* TO "
                      "'%(user)s'@'localhost' identified by '%(password)s'",
                      "grant SELECT on %(name)s.* TO 'nobody'@'%%'",
                      "grant SELECT on %(name)s.* TO 'nobody'@'localhost'",
                      "FLUSH PRIVILEGES"]

        if self.admin_connection is None:
            return False

        if not self.exists():
            return False

        self.admin_connection.begin()
        cursor = self.admin_connection.cursor()

        for cmd in grant_cmds:
            cmd_ = cmd % self.config_as_dict()
            try:
                cursor.execute(cmd_)
            except (MySQLdb.ProgrammingError, MySQLdb.OperationalError):
                self.admin_connection.rollback()
                return False

        self.admin_connection.commit()
        return True

    def setup(self):
        '''
        Performs all the steps neede to completely setup a database instance
        '''
        if self.admin_connection is None:
            logging.error("Failed to logon as the database admin user")
            return False

        self.admin_connection.begin()

        if not self.create_instance():
            self.admin_connection.rollback()
            return False

        if not self.grant_privileges():
            self.admin_connection.rollback()
            return False

        self.admin_connection.commit()
        return True
