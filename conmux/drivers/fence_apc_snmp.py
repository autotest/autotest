#!/usr/bin/python

#
#
#
# Copyright (C) Sistina Software, Inc.  1997-2003  All rights reserved.
# Copyright (C) 2004-2006 Red Hat, Inc.  All rights reserved.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions
# of the GNU General Public License v.2.
#
#
# This APC Fence script uses snmp to control the APC power
# switch. This script requires that net-snmp-utils be installed
# on all nodes in the cluster, and that the powernet369.mib file be
# located in /usr/share/snmp/mibs/
#
#


import getopt
import os
import select
import sys
import time
from glob import glob

# BEGIN_VERSION_GENERATION
FENCE_RELEASE_NAME = ""
REDHAT_COPYRIGHT = ""
BUILD_DATE = ""
# END_VERSION_GENERATION

POWER_ON = "outletOn"
POWER_OFF = "outletOff"
POWER_REBOOT = "outletReboot"


def usage():
    print("Usage:")
    print("")
    print("Options:")
    print("  -a <ip>          IP address or hostname of MasterSwitch")
    print("  -h               usage")
    print("  -l <name>        Login name")
    print("  -n <num>         Outlet number to change")
    print("  -o <string>      Action: Reboot (default), Off or On")
    print("  -p <string>      Login password")
    print("  -q               quiet mode")
    print("  -V               version")
    print("  -v               Log to file /tmp/apclog")

    print(sys.argv)
    sys.exit(0)


def main():
    apc_base = "enterprises.apc.products.hardware."
    apc_outletctl = "masterswitch.sPDUOutletControl.sPDUOutletControlTable.sPDUOutletControlEntry.sPDUOutletCtl."
    apc_outletstatus = "masterswitch.sPDUOutletStatus.sPDUOutletStatusMSPTable.sPDUOutletStatusMSPEntry.sPDUOutletStatusMSP."

    address = ""
    output = ""
    port = ""
    action = "outletReboot"
    status_check = False
    verbose = False

    if not glob('/usr/share/snmp/mibs/powernet*.mib'):
        sys.stderr.write('This APC Fence script uses snmp to control the APC power switch. This script requires that net-snmp-utils be installed on all nodes in the cluster, and that the powernet369.mib file be located in /usr/share/snmp/mibs/\n')
        sys.exit(1)

    if len(sys.argv) > 1:
        try:
            opts, args = getopt.getopt(sys.argv[1:], "a:hl:p:n:o:vV", ["help", "output="])
        except getopt.GetoptError:
            # print help info and quit
            usage()
            sys.exit(2)

        for o, a in opts:
            if o == "-v":
                verbose = True
            if o == "-V":
                print("%s\n" % FENCE_RELEASE_NAME)
                print("%s\n" % REDHAT_COPYRIGHT)
                print("%s\n" % BUILD_DATE)
                sys.exit(0)
            if o in ("-h", "--help"):
                usage()
                sys.exit(0)
            if o == "-n":
                port = a
            if o == "-o":
                lcase = a.lower()  # Lower case string
                if lcase == "off":
                    action = "outletOff"
                elif lcase == "on":
                    action = "outletOn"
                elif lcase == "reboot":
                    action = "outletReboot"
                elif lcase == "status":
                    #action = "sPDUOutletStatusMSPOutletState"
                    action = ""
                    status_check = True
                else:
                    usage()
                    sys.exit()
            if o == "-a":
                address = a

        if address == "":
            usage()
            sys.exit(1)

        if port == "":
            usage()
            sys.exit(1)

    else:  # Get opts from stdin
        params = {}
        # place params in dict
        for line in sys.stdin:
            val = line.split("=")
            if len(val) == 2:
                params[val[0].strip()] = val[1].strip()

        try:
            address = params["ipaddr"]
        except KeyError as e:
            sys.stderr.write("FENCE: Missing ipaddr param for fence_apc...exiting")
            sys.exit(1)
        try:
            login = params["login"]
        except KeyError as e:
            sys.stderr.write("FENCE: Missing login param for fence_apc...exiting")
            sys.exit(1)

        try:
            passwd = params["passwd"]
        except KeyError as e:
            sys.stderr.write("FENCE: Missing passwd param for fence_apc...exiting")
            sys.exit(1)

        try:
            port = params["port"]
        except KeyError as e:
            sys.stderr.write("FENCE: Missing port param for fence_apc...exiting")
            sys.exit(1)

        try:
            a = params["option"]
            if a == "Off" or a == "OFF" or a == "off":
                action = POWER_OFF
            elif a == "On" or a == "ON" or a == "on":
                action = POWER_ON
            elif a == "Reboot" or a == "REBOOT" or a == "reboot":
                action = POWER_REBOOT
        except KeyError as e:
            action = POWER_REBOOT

        # End of stdin section

    apc_command = apc_base + apc_outletctl + port

    args_status = list()
    args_off = list()
    args_on = list()

    args_status.append("/usr/bin/snmpget")
    args_status.append("-Oqu")  # sets printing options
    args_status.append("-v")
    args_status.append("1")
    args_status.append("-c")
    args_status.append("private")
    args_status.append("-m")
    args_status.append("ALL")
    args_status.append(address)
    args_status.append(apc_command)

    args_off.append("/usr/bin/snmpset")
    args_off.append("-Oqu")  # sets printing options
    args_off.append("-v")
    args_off.append("1")
    args_off.append("-c")
    args_off.append("private")
    args_off.append("-m")
    args_off.append("ALL")
    args_off.append(address)
    args_off.append(apc_command)
    args_off.append("i")
    args_off.append("outletOff")

    args_on.append("/usr/bin/snmpset")
    args_on.append("-Oqu")  # sets printing options
    args_on.append("-v")
    args_on.append("1")
    args_on.append("-c")
    args_on.append("private")
    args_on.append("-m")
    args_on.append("ALL")
    args_on.append(address)
    args_on.append(apc_command)
    args_on.append("i")
    args_on.append("outletOn")

    cmdstr_status = ' '.join(args_status)
    cmdstr_off = ' '.join(args_off)
    cmdstr_on = ' '.join(args_on)

# This section issues the actual commands. Reboot is split into
# Off, then On to make certain both actions work as planned.
#
# The status command just dumps the outlet status to stdout.
# The status checks that are made when turning an outlet on or off, though,
# use the execWithCaptureStatus so that the stdout from snmpget can be
# examined and the desired operation confirmed.

    if status_check:
        if verbose:
            fd = open("/tmp/apclog", "w")
            fd.write("Attempting the following command: %s\n" % cmdstr_status)
        strr = os.system(cmdstr_status)
        print(strr)
        if verbose:
            fd.write("Result: %s\n" % strr)
            fd.close()

    else:
        if action == POWER_OFF:
            if verbose:
                fd = open("/tmp/apclog", "w")
                fd.write("Attempting the following command: %s\n" % cmdstr_off)
            strr = os.system(cmdstr_off)
            time.sleep(1)
            strr, code = execWithCaptureStatus("/usr/bin/snmpget", args_status)
            if verbose:
                fd.write("Result: %s\n" % strr)
                fd.close()
            if strr.find(POWER_OFF) >= 0:
                print("Success. Outlet off")
                sys.exit(0)
            else:
                if verbose:
                    fd.write("Unable to power off apc outlet")
                    fd.close()
                sys.exit(1)

        elif action == POWER_ON:
            if verbose:
                fd = open("/tmp/apclog", "w")
                fd.write("Attempting the following command: %s\n" % cmdstr_on)
            strr = os.system(cmdstr_on)
            time.sleep(1)
            strr, code = execWithCaptureStatus("/usr/bin/snmpget", args_status)
            #strr = os.system(cmdstr_status)
            if verbose:
                fd.write("Result: %s\n" % strr)
            if strr.find(POWER_ON) >= 0:
                if verbose:
                    fd.close()
                print("Success. Outlet On.")
                sys.exit(0)
            else:
                print("Unable to power on apc outlet")
                if verbose:
                    fd.write("Unable to power on apc outlet")
                    fd.close()
                sys.exit(1)

        elif action == POWER_REBOOT:
            if verbose:
                fd = open("/tmp/apclog", "w")
                fd.write("Attempting the following command: %s\n" % cmdstr_off)
            strr = os.system(cmdstr_off)
            time.sleep(1)
            strr, code = execWithCaptureStatus("/usr/bin/snmpget", args_status)
            #strr = os.system(cmdstr_status)
            if verbose:
                fd.write("Result: %s\n" % strr)
            if strr.find(POWER_OFF) < 0:
                print("Unable to power off apc outlet")
                if verbose:
                    fd.write("Unable to power off apc outlet")
                    fd.close()
                sys.exit(1)

            if verbose:
                fd.write("Attempting the following command: %s\n" % cmdstr_on)
            strr = os.system(cmdstr_on)
            time.sleep(1)
            strr, code = execWithCaptureStatus("/usr/bin/snmpget", args_status)
            #strr = os.system(cmdstr_status)
            if verbose:
                fd.write("Result: %s\n" % strr)
            if strr.find(POWER_ON) >= 0:
                if verbose:
                    fd.close()
                print("Success: Outlet Rebooted.")
                sys.exit(0)
            else:
                print("Unable to power on apc outlet")
                if verbose:
                    fd.write("Unable to power on apc outlet")
                    fd.close()
                sys.exit(1)


def execWithCaptureStatus(command, argv, searchPath=0, root='/', stdin=0,
                          catchfd=1, closefd=-1):

    if not os.access(root + command, os.X_OK):
        raise RuntimeError(command + " cannot be run")

    (read, write) = os.pipe()

    childpid = os.fork()
    if (not childpid):
        if (root and root != '/'):
            os.chroot(root)
        if isinstance(catchfd, tuple):
            for fd in catchfd:
                os.dup2(write, fd)
        else:
            os.dup2(write, catchfd)
        os.close(write)
        os.close(read)

        if closefd != -1:
            os.close(closefd)

        if stdin:
            os.dup2(stdin, 0)
            os.close(stdin)

        if (searchPath):
            os.execvp(command, argv)
        else:
            os.execv(command, argv)

        sys.exit(1)

    os.close(write)

    rc = ""
    s = "1"
    while (s):
        select.select([read], [], [])
        s = os.read(read, 1000)
        rc = rc + s

    os.close(read)

    pid = -1
    status = -1
    try:
        (pid, status) = os.waitpid(childpid, 0)
    except OSError, (errno, msg):
        print(__name__, "waitpid:", msg)

    if os.WIFEXITED(status) and (os.WEXITSTATUS(status) == 0):
        status = os.WEXITSTATUS(status)
    else:
        status = -1

    return (rc, status)


if __name__ == "__main__":
    main()
