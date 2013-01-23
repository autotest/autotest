def migrate_up(manager):
    manager.execute('ALTER TABLE autotests ADD `synch_type` smallint '
                    'NOT NULL')
    # set all to asynchronous by default
    manager.execute('UPDATE autotests SET synch_type=1')


def migrate_down(manager):
    manager.execute('ALTER TABLE autotests DROP `synch_type`')
