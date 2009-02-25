def migrate_up(mgr):
    mgr.execute("alter table machines modify column hostname varchar(1000);")

def migrate_down(mgr):
    mgr.execute("alter table machines modify column hostname varchar(100);")
