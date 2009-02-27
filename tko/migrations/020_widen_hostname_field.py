def migrate_up(mgr):
    mgr.execute("alter table machines modify column hostname varchar(700);")

def migrate_down(mgr):
    mgr.execute("alter table machines modify column hostname varchar(100);")
