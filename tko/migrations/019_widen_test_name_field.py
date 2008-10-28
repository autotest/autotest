def migrate_up(mgr):
    mgr.execute("alter table tests modify column test varchar(60);")

def migrate_down(mgr):
    mgr.execute("alter table tests modify column test varchar(30);")
