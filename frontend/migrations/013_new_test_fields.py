def migrate_up(manager):
    manager.execute('ALTER TABLE jobs ADD run_verify tinyint(1) default 1')
    manager.execute('ALTER TABLE autotests ADD author VARCHAR(256)')
    manager.execute('ALTER TABLE autotests ADD dependencies VARCHAR(256)')
    manager.execute('ALTER TABLE autotests ADD experimental SMALLINT DEFAULT 0')
    manager.execute('ALTER TABLE autotests ADD run_verify SMALLINT DEFAULT 1')
    manager.execute('ALTER TABLE autotests ADD test_time SMALLINT DEFAULT 1')
    manager.execute('ALTER TABLE autotests ADD test_category VARCHAR(256)')
    manager.execute('ALTER TABLE autotests ADD sync_count INT(11) DEFAULT 1')


def migrate_down(manager):
    manager.execute('ALTER TABLE jobs DROP run_verify')
    manager.execute('ALTER TABLE autotests DROP sync_count')
    manager.execute('ALTER TABLE autotests DROP author')
    manager.execute('ALTER TABLE autotests DROP dependencies')
    manager.execute('ALTER TABLE autotests DROP experimental')
    manager.execute('ALTER TABLE autotests DROP run_verify')
    manager.execute('ALTER TABLE autotests DROP test_time')
    manager.execute('ALTER TABLE autotests DROP test_category')
