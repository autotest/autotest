def migrate_up(manager):
    manager.execute('UPDATE users SET access_level = 0')

def migrate_down(manager):
    pass
