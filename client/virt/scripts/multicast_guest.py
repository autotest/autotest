#!/usr/bin/python
import socket, struct, os, signal, sys
# -*- coding: utf-8 -*-

"""
Script used to join machine into multicast groups.

@author Amos Kong <akong@redhat.com>
"""

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print """%s [mgroup_count] [prefix] [suffix]
        mgroup_count: count of multicast addresses
        prefix: multicast address prefix
        suffix: multicast address suffix""" % sys.argv[0]
        sys.exit()

    mgroup_count = int(sys.argv[1])
    prefix = sys.argv[2]
    suffix = int(sys.argv[3])

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    for i in range(mgroup_count):
        mcast = prefix + "." + str(suffix + i)
        try:
            mreq = struct.pack("4sl", socket.inet_aton(mcast),
                               socket.INADDR_ANY)
            s.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        except:
            s.close()
            print "Could not join multicast: %s" % mcast
            raise

    print "join_mcast_pid:%s" % os.getpid()
    os.kill(os.getpid(), signal.SIGSTOP)
    s.close()
