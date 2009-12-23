import migrate


def drop_views(manager, views):
    """
    Drops the specified views from the database

    If a specified view does not exist in the database, this method fails
    without modification

    @param manager the migration manager
    @param views the views to drop
    """
    _check_exists(manager, views, 'VIEW')
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
    _check_exists(manager, (table for table, _ in mapping.iteritems()), 'TABLE')
    for orig_name, new_name in mapping.iteritems():
        manager.execute('RENAME TABLE `%s` TO `%s`' % (orig_name, new_name))


def _check_exists(manager, names, type):
    """
    Checks if the tables or views exists.

    Raise an Exception if any of the names do not exist

    @param manager the migration manager
    @param names the table/view names
    @param type one of 'TABLE' or 'VIEW'
    """
    if type == 'TABLE':
        info_table = 'TABLES'
    elif type == 'VIEW':
        info_table = 'VIEWS'
    else:
        raise Exception("type parameter must be either 'TABLE' or 'VIEW'")

    query = ('SELECT table_name FROM information_schema.%s '
             'WHERE table_schema = %%s' % info_table)
    rows = manager.execute(query, manager.get_db_name())
    existing_names = [row[0] for row in rows]

    for name in names:
        if name not in existing_names:
            raise Exception('%s missing from database, stopping' % name)
