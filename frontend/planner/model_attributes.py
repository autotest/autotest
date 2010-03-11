import common
from autotest_lib.client.common_lib import enum


# common enums for Host attributes
HostStatus = enum.Enum('Finished', 'Running', 'Blocked', string_values=True)


# common enums for TestRun attributes
TestRunStatus = enum.Enum('Active', 'Passed', 'Failed', string_values=True)


# common enums for SavedObject attributes
SavedObjectType = enum.Enum('support', 'triage', 'autoprocess', 'custom_query',
                            string_values=True)
