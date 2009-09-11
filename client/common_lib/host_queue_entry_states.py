"""
This module contains the status enums for use by HostQueueEntrys in the
database.  It is a stand alone module as these status strings are needed
from various disconnected pieces of code that should not depend on everything
that frontend.afe.models depends on such as RPC clients.
"""

from autotest_lib.client.common_lib import enum

Status = enum.Enum('Queued', 'Starting', 'Verifying', 'Pending', 'Running',
                   'Gathering', 'Parsing', 'Aborted', 'Completed',
                   'Failed', 'Stopped', 'Template', 'Waiting',
                   string_values=True)
ACTIVE_STATUSES = (Status.STARTING, Status.VERIFYING, Status.PENDING,
                   Status.RUNNING, Status.GATHERING)
COMPLETE_STATUSES = (Status.ABORTED, Status.COMPLETED, Status.FAILED,
                     Status.STOPPED, Status.TEMPLATE)
