def migrate_up(manager):
	manager.execute('ALTER TABLE autotests DROP params')
	manager.execute('ALTER TABLE jobs DROP kernel_url, DROP status, '
			'DROP submitted_on')
	manager.execute('ALTER TABLE host_queue_entries DROP created_on')
