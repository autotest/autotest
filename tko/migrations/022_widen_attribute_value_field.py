def migrate_up(mgr):
    mgr.execute("alter table test_attributes modify column value varchar(1024);")
    mgr.execute("alter table iteration_attributes modify column value varchar(1024);")

def migrate_down(mgr):
    mgr.execute("alter table test_attributes modify column value varchar(100);")
    mgr.execute("alter table iteration_attributes modify column value varchar(100);")
