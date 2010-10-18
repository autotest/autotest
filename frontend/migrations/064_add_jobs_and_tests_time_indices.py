# These indices speed up date-range queries often used in making dashboards.
UP_SQL = """
alter table tko_tests add index started_time (started_time);
alter table afe_jobs add index created_on (created_on);
"""

DOWN_SQL = """
drop index started_time on tko_tests;
drop index created_on on afe_jobs;
"""
