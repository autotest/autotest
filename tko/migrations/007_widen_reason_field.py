def migrate_up(mgr):
    mgr.execute("alter table tests modify column reason varchar(1024);")

def migrate_down(mgr):
    mgr.execute("alter table tests modify column reason varchar(100);")
