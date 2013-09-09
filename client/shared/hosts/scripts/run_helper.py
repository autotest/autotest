#!/usr/bin/python
# encoding: utf-8
"""
run_helper takes care about running command when parent process dies.

It kills children when parent process dies.
"""
import sys
import os
import signal
import select


def main():
    argv = sys.argv
    shell_pid = os.fork()
    if shell_pid == 0:
        # Child process: run the command in a subshell
        os.execv("/bin/sh", ["/bin/sh", "-c"] + [" ".join(argv[1:])])
    else:
        def die_handler(signum, frame):
            """
            Handler is called when child process died.
            """
            (pid, status) = os.waitpid(shell_pid, 0)
            sys.exit(status >> 8)

        signal.signal(signal.SIGCHLD, die_handler)
        select.select([sys.stdin.fileno()], [], [])
        os.kill(shell_pid, signal.SIGKILL)
        return 0


if __name__ == "__main__":
    sys.exit(main())
