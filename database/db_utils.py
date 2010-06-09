TABLE_TYPE = object()
VIEW_TYPE = object()


class NameMissingException(Exception):
    pass


def drop_views(manager, views):
    """
    Drops the specified views from the database

    If a specified view does not exist in the database, this method fails
    without modification

    @param manager the migration manager
    @param views the views to drop
    """
    check_exists(manager, views, VIEW_TYPE)
    for view in views:
        manager.execute('DROP VIEW `%s`' % view)


def rename(manager, mapping):
    """
    Renames specified tables in the database

    Use this to rename a specified set of tables in a database. If a source in
    the mapping does not exist, this method fails without modification.

    @param manager the migration manager
    @param mapping a dictionary of orig_name => new_name. Any table not matching
                   an entry in this dictionary will not be renamed
    """
    check_exists(manager, (table for table, _ in mapping.iteritems()),
                  TABLE_TYPE)
    for orig_name, new_name in mapping.iteritems():
        manager.execute('RENAME TABLE `%s` TO `%s`' % (orig_name, new_name))


def move_tables(manager, src_manager, tables):
    """
    Moves the specified tables from another database

    If a table does not exist in the source database, this method fails without
    modification

    @param manager the migration manager
    @param src_manager a migration manager that handles the source database
    @param tables a list of tables to move
    """
    check_exists(src_manager, tables, TABLE_TYPE)
    for table in tables:
        manager.execute('RENAME TABLE `%(db)s`.`%(table)s` TO `%(table)s`'
                        % dict(db=src_manager.get_db_name(), table=table))


def drop_database(manager):
    """
    Drops the database that the specified manager controls

    @param manager the migration manager
    """
    manager.execute('DROP DATABASE `%s`' % manager.get_db_name())


def check_exists(manager, names, type):
    """
    Checks if the tables or views exists.

    Raise an Exception if any of the names do not exist

    @param manager the migration manager
    @param names the table/view names
    @param type one of 'TABLE' or 'VIEW'
    """
    if type == TABLE_TYPE:
        info_table = 'TABLES'
    elif type == VIEW_TYPE:
        info_table = 'VIEWS'
    else:
        raise Exception("type parameter must be either TABLE_TYPE or VIEW_TYPE")

    query = ('SELECT table_name FROM information_schema.%s '
             'WHERE table_schema = %%s' % info_table)
    rows = manager.execute(query, manager.get_db_name())
    existing_names = [row[0] for row in rows]

    for name in names:
        if name not in existing_names:
            raise NameMissingException(
                    '%s missing from database, stopping' % name)


def check_index_exists(manager, table_name, index_name):
    """
    Checks if a particular index exists on the table

    @param manager the migration manager
    @param table_name the table to check
    @param index_name the index to check
    """
    query = ('SELECT 1 FROM information_schema.statistics '
             'WHERE table_schema = %s AND table_name = %s AND index_name = %s')
    rows = manager.execute(query, manager.get_db_name(), table_name, index_name)
    return bool(rows)


DJANGO_AUTH_TABLES = ('auth_group', 'auth_group_permissions', 'auth_permission')

def auth_tables_exist(manager):
    try:
        check_exists(manager, DJANGO_AUTH_TABLES, TABLE_TYPE)
        return True
    except NameMissingException:
        return False
