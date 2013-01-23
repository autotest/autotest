UP_SQL = """
ALTER TABLE tko_tests MODIFY test varchar(300) default NULL;
ALTER TABLE tko_tests MODIFY subdir varchar(300) default NULL;
"""

DOWN_SQL = """
ALTER TABLE tko_tests MODIFY test varchar(60) default NULL;
ALTER TABLE tko_tests MODIFY subdir varchar(60) default NULL;
"""
