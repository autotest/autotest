import common
from autotest_lib.client.common_lib import enum


# common enums for Job attributes
RebootBefore = enum.Enum('Never', 'If dirty', 'Always')
RebootAfter = enum.Enum('Never', 'If all tests passed', 'Always')


# common enums for test attributes
TestTypes = enum.Enum('Client', 'Server', start_value=1)
