UP_SQL = """
CREATE UNIQUE INDEX host_queue_entries_job_id_and_host_id
ON host_queue_entries (job_id, host_id);

DROP INDEX host_queue_entries_job_id ON host_queue_entries;
"""


DOWN_SQL = """
CREATE INDEX host_queue_entries_job_id ON host_queue_entries (job_id);

DROP INDEX host_queue_entries_job_id_and_host_id ON host_queue_entries;
"""


def null_out_duplicate_hqes(manager, hqe_ids):
    if not hqe_ids:
        return
    ids_to_null_string = ','.join(str(hqe_id) for hqe_id in hqe_ids)

    # check if any of the HQEs we're going to null out are active. if so, it's
    # too dangerous to proceed.
    rows = manager.execute('SELECT id FROM host_queue_entries '
                           'WHERE active AND id IN (%s)' % ids_to_null_string)
    if rows:
        raise Exception('Active duplicate HQEs exist, cannot proceed.  Please '
                        'manually abort these HQE IDs: %s' % ids_to_null_string)

    # go ahead and null them out
    print 'Nulling out duplicate HQE IDs: %s' % ids_to_null_string
    manager.execute('UPDATE host_queue_entries '
                    'SET host_id = NULL, active = FALSE, complete = TRUE, '
                    'aborted = TRUE, status = "Aborted" '
                    'WHERE id IN (%s)' % ids_to_null_string)


def migrate_up(manager):
    # cleanup duplicate host_queue_entries. rather than deleting them (and
    # dealing with foreign key references), we'll just null out their host_ids
    # and set them to aborted.
    rows = manager.execute('SELECT GROUP_CONCAT(id), COUNT(1) AS count '
                           'FROM host_queue_entries '
                           'WHERE host_id IS NOT NULL '
                           'GROUP BY job_id, host_id HAVING count > 1')
    # gather all the HQE IDs we want to null out
    ids_to_null = []
    for ids_string, _ in rows:
        id_list = ids_string.split(',')
        # null out all but the first one.  this isn't terribly important, but
        # the first one is the most likely to have actually executed, so might
        # as well keep that one.
        ids_to_null.extend(id_list[1:])

    null_out_duplicate_hqes(manager, ids_to_null)

    manager.execute_script(UP_SQL)
