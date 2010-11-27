#
# Copyright 2007 Google Inc. All Rights Reserved.

"""Runs profilers on a machine when no autotest job is running.

This is used to profile a task when the task is running on a machine that is not
running through autotest.
"""

__author__ = 'cranger@google.com (Colby Ranger)'

import platform
import common
from autotest_lib.client.common_lib import barrier

# Client control file snippet used to synchronize profiler start & stop.
_RUNTEST_PATTERN = ("job.run_test('profiler_sync', timeout_sync=%r,\n"
                    "             timeout_start=%r, timeout_stop=%r,\n"
                    "             hostid='%s', masterid='%s', all_ids=%r)")
_PROF_MASTER = platform.node()
_PORT = 11920


def _encode_args(profiler, args, dargs):
    parts = [repr(profiler)]
    parts += [repr(arg) for arg in args]
    parts += ["%s=%r" % darg for darg in dargs.iteritems()]
    return ", ".join(parts)


def generate_test(machines, hostname, profilers, timeout_start, timeout_stop,
                  timeout_sync=180):
    """
    Generate a control file that enables profilers and starts profiler_sync.

    @param machines: sequence of all the hostnames involved in the barrier
            synchronization
    @param hostname: hostname of the machine running the generated control file
    @param profilers: a sequence of 3 items tuples where the first item is a
            string (the profiler name), second argument is a tuple with the
            non keyword arguments to give to the profiler when being added
            with "job.profilers.add()" in the control file, third item is
            a dictionary of the keyword arguments to give it
    @param timeout_start: how many seconds to wait in profiler_sync for the
            profilers to start (None means no timeout)
    @param timeout_stop: how many seconds to wait in profiler_sync for the
            profilers to stop (None means no timeout)
    @param timeout_sync: how many seconds to wait in profiler_sync for other
            machines to reach the start of the profiler_sync (None means no
            timeout)
    """
    control_file = []
    for profiler in profilers:
        control_file.append("job.profilers.add(%s)"
                            % _encode_args(*profiler))

    profiler_sync_call = (_RUNTEST_PATTERN %
                          (timeout_sync, timeout_start, timeout_stop,
                           hostname, _PROF_MASTER, machines))
    control_file.append(profiler_sync_call)

    for profiler in reversed(profilers):
        control_file.append("job.profilers.delete('%s')" % profiler[0])

    return "\n".join(control_file)


def wait_for_profilers(machines, timeout=300):
    sb = barrier.barrier(_PROF_MASTER, "sync_profilers",
            timeout, port=_PORT)
    sb.rendezvous_servers(_PROF_MASTER, *machines)


def start_profilers(machines, timeout=120):
    sb = barrier.barrier(_PROF_MASTER, "start_profilers",
            timeout, port=_PORT)
    sb.rendezvous_servers(_PROF_MASTER, *machines)


def stop_profilers(machines, timeout=120):
    sb = barrier.barrier(_PROF_MASTER, "stop_profilers",
            timeout, port=_PORT)
    sb.rendezvous_servers(_PROF_MASTER, *machines)


def finish_profilers(machines, timeout=120):
    sb = barrier.barrier(_PROF_MASTER, "finish_profilers",
            timeout, port=_PORT)
    sb.rendezvous_servers(_PROF_MASTER, *machines)
