"""
This module contains the status enums for use by HostQueueEntrys in the
database.  It is a stand alone module as these status strings are needed
from various disconnected pieces of code that should not depend on everything
that autotest.frontend.afe.models depends on such as RPC clients.
"""

from autotest.client.shared import enum

Status = enum.Enum('Queued', 'Starting', 'Verifying', 'Pending', 'Waiting',
                   'Running', 'Gathering', 'Parsing', 'Archiving', 'Aborted',
                   'Completed', 'Failed', 'Stopped', 'Template',
                   string_values=True)
ACTIVE_STATUSES = (Status.STARTING, Status.VERIFYING, Status.PENDING,
                   Status.RUNNING, Status.GATHERING)
COMPLETE_STATUSES = (Status.ABORTED, Status.COMPLETED, Status.FAILED,
                     Status.STOPPED, Status.TEMPLATE)
