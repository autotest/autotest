def migrate_up(manager):
    manager.execute('ALTER TABLE autotests DROP params')
    manager.execute('ALTER TABLE jobs DROP kernel_url, DROP status, '
                    'DROP submitted_on')
    manager.execute('ALTER TABLE host_queue_entries DROP created_on')

def migrate_down(manager):
    manager.execute('ALTER TABLE autotests ADD params VARCHAR(255)')
    manager.execute('ALTER TABLE jobs ADD kernel_url VARCHAR(255), '
                    'ADD status VARCHAR(255), ADD submitted_on datetime')
    manager.execute('ALTER TABLE host_queue_entries ADD created_on '
                    'datetime')
