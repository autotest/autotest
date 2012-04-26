try:
    import autotest.common as common
except ImportError:
    import common
from autotest.client.shared import enum


# common enums for Job attributes
RebootBefore = enum.Enum('Never', 'If dirty', 'Always')
RebootAfter = enum.Enum('Never', 'If all tests passed', 'Always')


# common enums for test attributes
TestTypes = enum.Enum('Client', 'Server', start_value=1)


# common enums for profiler and job parameter types
ParameterTypes = enum.Enum('int', 'float', 'string', string_values=True)
