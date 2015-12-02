try:
    import autotest.common as common  # pylint: disable=W0611
except ImportError:
    import common  # pylint: disable=W0611
from autotest.client.shared import enum


# common enums for Job attributes
RebootBefore = enum.Enum('Never', 'If dirty', 'Always')
RebootAfter = enum.Enum('Never', 'If all tests passed', 'Always')


# common enums for test attributes
TestTypes = enum.Enum('Client', 'Server', start_value=1)


# common enums for profiler and job parameter types
ParameterTypes = enum.Enum('int', 'float', 'string', string_values=True)
