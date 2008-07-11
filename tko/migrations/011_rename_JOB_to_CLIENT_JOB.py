JOB_TO_CLIENT_JOB = """UPDATE tests SET test='CLIENT_JOB' WHERE test='JOB';"""

CLIENT_JOB_TO_JOB = """UPDATE tests SET test='JOB' WHERE test='CLIENT_JOB';"""


def migrate_up(manager):
    manager.execute_script(JOB_TO_CLIENT_JOB)


def migrate_down(manager):
    manager.execute_script(CLIENT_JOB_TO_JOB)
