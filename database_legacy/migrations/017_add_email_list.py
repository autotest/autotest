def migrate_up(manager):
    manager.execute(ADD_COLUMN)

def migrate_down(manager):
    manager.execute(DROP_COLUMN)

ADD_COLUMN = 'ALTER TABLE jobs ADD COLUMN email_list varchar(250) NOT NULL'
DROP_COLUMN = 'ALTER TABLE jobs DROP COLUMN email_list'
