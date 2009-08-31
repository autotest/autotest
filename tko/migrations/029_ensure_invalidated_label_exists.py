# the "invalidated" test label is used implicitly by TKO for (you guessed it)
# invalidating test results.  if it doesn't exist in the DB, errors will show
# up.

def migrate_up(manager):
    rows = manager.execute(
            'SELECT * FROM test_labels WHERE name = "invalidated"')
    if not rows:
        manager.execute('INSERT INTO test_labels SET name = "invalidated", '
                        'description = "Used by TKO to invalidate tests"')


def migrate_down(manager):
    # no need to remove the label
    pass
