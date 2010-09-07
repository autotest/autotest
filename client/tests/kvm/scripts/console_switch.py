#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Auxiliary script used to send data between ports on guests.

@copyright: 2008-2009 Red Hat Inc.
@author: Jiri Zupka (jzupka@redhat.com)
@author: Lukas Doktor (ldoktor@redhat.com)
"""
import threading
from threading import Thread
import os,time,select,re,random,sys,array

files = {}
ev = threading.Event()
threads = []

DEBUGPATH="/sys/kernel/debug"


class Switch(Thread):
    """
    Create a thread which sends data between ports.
    """
    def __init__(self, exitevent, in_files, out_files, cachesize=1):
        """
        @param exitevent: Event to end switch.
        @param in_files: Array of input files.
        @param out_files: Array of output files.
        @param cachesize: Block to receive and send.
        """
        Thread.__init__(self)

        self.in_files = in_files
        self.out_files = out_files

        self.cachesize = cachesize
        self.exitevent = exitevent


    def run(self):
        while not self.exitevent.isSet():
            #TODO: Why select causes trouble? :-(
            #ret = select.select(self.in_files,[],[],1.0)
            data = ""
            #if not ret[0] == []:
            for desc in self.in_files:
                data += os.read(desc, self.cachesize)
            for desc in self.out_files:
                os.write(desc, data)


class Sender(Thread):
    """
    Creates thread which sends random blocks of data to the destination port.
    """
    def __init__(self, port, length):
        """
        @param port: Destination port.
        @param length: Length of the random data block.
        """
        Thread.__init__(self)
        self.port = port
        self.data = array.array('L')
        for i in range(max(length/self.data.itemsize, 1)):
            self.data.append(random.randrange(sys.maxint))


    def run(self):
        while True:
            os.write(self.port, self.data)
        del threads[:]


def get_port_status():
    """
    Get info about ports from kernel debugfs.

    @return: ports dictionary of port properties
    """
    ports = {}

    not_present_msg = "FAIL: There's no virtio-ports dir in debugfs"
    if not os.path.ismount(DEBUGPATH):
        os.system('mount -t debugfs none %s' % DEBUGPATH)
    try:
        if not os.path.isdir('%s/virtio-ports' % DEBUGPATH):
            print not_present_msg
    except:
        print not_present_msg
    else:
        viop_names = os.listdir('%s/virtio-ports' % DEBUGPATH)
        for name in viop_names:
            f = open("%s/virtio-ports/%s" % (DEBUGPATH, name), 'r')
            port = {}
            for line in iter(f):
                m = re.match("(\S+): (\S+)",line)
                port[m.group(1)] = m.group(2)

            if (port['is_console'] == "yes"):
                port["path"] = "/dev/hvc%s" % port["console_vtermno"]
                # Console works like a serialport
            else:
                port["path"] = "/dev/%s" % name
            ports[port['name']] = port
            f.close()

    return ports


def open_device(in_files, ports):
    """
    Open devices and return an array of descriptors.

    @param in_files: files array
    @return: array of descriptors
    """
    f = []

    for item in in_files:
        name = ports[item[0]]["path"]
        if (not item[1] == ports[item[0]]["is_console"]):
            print ports
            print "FAIL: Host console is not like console on guest side\n"

        if (name in files):
            f.append(files[name])
        else:
            try:
                files[name] = os.open(name, os.O_RDWR)
                if (ports[item[0]]["is_console"] == "yes"):
                    print os.system("stty -F %s raw -echo" %
                                    (ports[item[0]]["path"]))
                    print os.system("stty -F %s -a" % ports[item[0]]["path"])
                f.append(files[name])
            except Exception as inst:
                print "FAIL: Failed to open file %s" % name
                raise inst
    return f


def start_switch(in_files,out_files,cachesize=1):
    """
    Start a switch thread
    (because there is a problem with opening one file multiple times).

    @param in_files: array of input files
    @param out_files: array of output files
    @param cachesize: cachesize
    """
    ports = get_port_status()

    in_f = open_device(in_files, ports)
    out_f = open_device(out_files, ports)

    s = Switch(ev, in_f, out_f, cachesize)
    s.start()
    threads.append(s)

    print "PASS: Start switch"


def end_switches():
    """
    End all running data switches.
    """
    ev.set()
    for th in threads:
        print "join"
        th.join(3.0)
    ev.clear()

    del threads[:]
    print "PASS: End switch"


def die():
    """
    Quit consoleswitch.
    """
    for desc in files.itervalues():
        os.close(desc)
    current_pid = os.getpid()
    os.kill(current_pid, 15)


def sender_prepare(port, length):
    """
    Prepares the sender thread. Requires a clean thread structure.
    """
    del threads[:]
    ports = get_port_status()
    in_f = open_device([port], ports)

    threads.append(Sender(in_f[0], length))
    print "PASS: Sender prepare"


def sender_start():
    """
    Start sender data transfer. Requires sender_prepare to run first.
    """
    threads[0].start()
    print "PASS: Sender start"


def main():
    """
    Main (infinite) loop of console_switch.
    """
    print "PASS: Start"
    end = False
    while not end:
        str = raw_input()
        exec str


if __name__ == "__main__":
    main()
