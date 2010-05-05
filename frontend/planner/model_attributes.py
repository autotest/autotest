import common
from autotest_lib.client.common_lib import enum, utils


# common enums for Host attributes
HostStatus = enum.Enum('Finished', 'Running', 'Blocked', string_values=True)


# common enums for TestRun attributes
TestRunStatus = enum.Enum('Active', 'Passed', 'Failed', string_values=True)


# common enums for SavedObject attributes
SavedObjectType = enum.Enum('support', 'triage', 'autoprocess', 'custom_query',
                            string_values=True)


# common enums for AdditionalParameter attributes
def _site_additional_parameter_types_dummy():
    return []
_site_additional_parameter_types = utils.import_site_function(
        __file__, 'autotest_lib.frontend.planner.site_model_attributes',
        'site_additional_parameter_types',
        _site_additional_parameter_types_dummy)
AdditionalParameterType = enum.Enum(
        string_values=True,
        *(_site_additional_parameter_types() + ['Verify']))
