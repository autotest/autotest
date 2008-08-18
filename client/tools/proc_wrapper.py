#!/usr/bin/python2.4

import os, subprocess, sys, time

def print_cpu_usage(args):
    """Wraps the given command and prints out the average CPU usage.

    args should either be the full string to execute or a list containing
    the executable name followed by all arguments as specified in the
    subprocess.Popen doc
    """

    # Open the process
    p = subprocess.Popen(args)

    # Sample process's CPU usage every so often until terminated
    cpu = []
    while os.waitpid(p.pid, os.WNOHANG) == (0,0):
        p2 = subprocess.Popen(['ps','-o %C', '--no-headers',str(p.pid)],
                              stdout=subprocess.PIPE)
        stdout = p2.communicate()[0]
        cpu.append(float(stdout.strip()))
        time.sleep(0.1)

    try:
        # Purge leading zeros
        while cpu[0] == 0:
            cpu.pop(0)

        print "CPU: %.2f%% -- %d samples" % (sum(cpu)/len(cpu), len(cpu))
    except IndexError:
        print "CPU: 0.00%% -- 0 samples"


if __name__ == '__main__':
    print_cpu_usage(sys.argv[1:])
