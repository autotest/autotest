def execute_safely(manager, statement):
    try:
        manager.execute(statement)
    except Exception:
        print 'Statement %r failed (this is not fatal)' % statement


def delete_duplicates(manager, table, first_id, second_id):
    rows = manager.execute(
        'SELECT %s, %s, COUNT(1) AS count FROM %s '
        'GROUP BY %s, %s HAVING count > 1' %
        (first_id, second_id, table, first_id, second_id))
    for first_id_value, second_id_value, count_unused in rows:
        manager.execute('DELETE FROM %s '
                        'WHERE %s = %%s AND %s = %%s LIMIT 1' %
                        (table, first_id, second_id),
                        first_id_value, second_id_value)
    if rows:
        print 'Deleted %s duplicate rows from %s' % (len(rows), table)


def delete_invalid_foriegn_keys(manager, pivot_table, foreign_key_field,
                                destination_table):
    manager.execute(
        'DELETE %(table)s.* FROM %(table)s '
        'LEFT JOIN %(destination_table)s '
        'ON %(table)s.%(field)s = %(destination_table)s.id '
        'WHERE %(destination_table)s.id IS NULL' %
        dict(table=pivot_table, field=foreign_key_field,
             destination_table=destination_table))
    deleted_count = manager._database.rowcount
    if deleted_count:
        print ('Deleted %s invalid foreign key references from %s (%s)' %
               (deleted_count, pivot_table, foreign_key_field))


def unique_index_name(table):
    return table + '_both_ids'


def basic_index_name(table, field):
    if field == 'aclgroup_id':
        field = 'acl_group_id'
    return table + '_' + field


def create_unique_index(manager, pivot_table, first_field, second_field):
    index_name = unique_index_name(pivot_table)
    manager.execute('CREATE UNIQUE INDEX %s ON %s (%s, %s)' %
                    (index_name, pivot_table, first_field, second_field))

    # these indices are in the migrations but may not exist for historical
    # reasons
    old_index_name = basic_index_name(pivot_table, first_field)
    execute_safely(manager, 'DROP INDEX %s ON %s' %
                   (old_index_name, pivot_table))


def drop_unique_index(manager, pivot_table, first_field):
    index_name = unique_index_name(pivot_table)
    manager.execute('DROP INDEX %s ON %s' % (index_name, pivot_table))

    old_index_name = basic_index_name(pivot_table, first_field)
    manager.execute('CREATE INDEX %s ON %s (%s)' %
                    (old_index_name, pivot_table, first_field))


def foreign_key_name(table, field):
    return '_'.join([table, field, 'fk'])


def create_foreign_key_constraint(manager, table, field, destination_table):
    key_name = foreign_key_name(table, field)
    manager.execute('ALTER TABLE %s ADD CONSTRAINT %s FOREIGN KEY (%s) '
                    'REFERENCES %s (id) ON DELETE NO ACTION' %
                    (table, key_name, field, destination_table))


def drop_foreign_key_constraint(manager, table, field):
    key_name = foreign_key_name(table, field)
    manager.execute('ALTER TABLE %s DROP FOREIGN KEY %s' % (table, key_name))


def cleanup_m2m_pivot(manager, pivot_table, first_field, first_table,
                      second_field, second_table, create_unique):
    delete_duplicates(manager, pivot_table, first_field, second_field)
    delete_invalid_foriegn_keys(manager, pivot_table, first_field, first_table)
    delete_invalid_foriegn_keys(manager, pivot_table, second_field,
                                second_table)

    if create_unique:
        # first field is the more commonly used one, so we'll replace the
        # less-commonly-used index with the larger unique index
        create_unique_index(manager, pivot_table, second_field, first_field)

    create_foreign_key_constraint(manager, pivot_table, first_field,
                                  first_table)
    create_foreign_key_constraint(manager, pivot_table, second_field,
                                  second_table)


def reverse_cleanup_m2m_pivot(manager, pivot_table, first_field, second_field,
                              drop_unique):
    drop_foreign_key_constraint(manager, pivot_table, second_field)
    drop_foreign_key_constraint(manager, pivot_table, first_field)
    if drop_unique:
        drop_unique_index(manager, pivot_table, second_field)


TABLES = (
        ('hosts_labels', 'host_id', 'hosts', 'label_id', 'labels', True),
        ('acl_groups_hosts', 'host_id', 'hosts', 'aclgroup_id', 'acl_groups',
         True),
        ('acl_groups_users', 'user_id', 'users', 'aclgroup_id', 'acl_groups',
         True),
        ('autotests_dependency_labels', 'test_id', 'autotests', 'label_id',
         'labels', False),
        ('jobs_dependency_labels', 'job_id', 'jobs', 'label_id', 'labels',
         False),
        ('ineligible_host_queues', 'job_id', 'jobs', 'host_id', 'hosts', True),
    )


def migrate_up(manager):
    for (table, first_field, first_table, second_field, second_table,
         create_unique) in TABLES:
        cleanup_m2m_pivot(manager, table, first_field, first_table,
                          second_field, second_table, create_unique)


def migrate_down(manager):
    for (table, first_field, first_table, second_field, second_table,
         drop_unique) in reversed(TABLES):
        reverse_cleanup_m2m_pivot(manager, table, first_field, second_field,
                                  drop_unique)
