"""
Abstraction layer for managing different database systems

This is not a reinvention or reimplementation of Python's DB API, but a simple
API for for creating, populating and removing instances transparently.
"""

import logging

from autotest.client.shared import settings

from dummy import DummyDatabaseManager
from mysql import MySQLDatabaseManager


#
# FIXME: this should not be a static registry assigment but a dynamic import
# because the way it's done now, it requires all python database interface
# modules to be present
#
RDBMS_REGISTRY = {'mysql': MySQLDatabaseManager}


def get_manager_class(rdbms_type):
    '''
    Returns a manager class for a given RDBMS type
    '''
    klass = RDBMS_REGISTRY.get(rdbms_type, None)
    if klass is None:
        logging.info('There\'s no database manager specific for "%s"',
                     rdbms_type)
        klass = DummyDatabaseManager
    return klass


def engine_to_rdbms_type(django_engine):
    '''
    Returns a RDBMS type for a given django engine name
    '''
    rdbms_type = django_engine.split('.')[-1]

    if rdbms_type == 'afe':
        rdbms_type = 'mysql'
    elif rdbms_type.startswith('afe_'):
        rdbms_type = rdbms_type[4:]
    return rdbms_type


def get_manager_class_from_engine(django_engine):
    '''
    Returns a manager class for a given django engine
    '''
    rdbms_type = engine_to_rdbms_type(django_engine)
    return get_manager_class(rdbms_type)


def get_manager_from_config(admin_password=None, rdbms_type=None):
    '''
    Returns a manager instance from the information on the configuration file
    '''
    sect = 'AUTOTEST_WEB'
    name = settings.settings.get_value(sect, 'database')
    user = settings.settings.get_value(sect, 'user')
    password = settings.settings.get_value(sect, 'password')
    host = settings.settings.get_value(sect, 'host')

    if rdbms_type is None:
        rdbms_type = settings.settings.get_value(sect, 'db_type')

    klass = get_manager_class(rdbms_type)
    manager = klass(name, admin_password=admin_password, user=user,
                    password=password, host=host)

    return manager
