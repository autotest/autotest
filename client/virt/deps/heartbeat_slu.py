#!/usr/bin/env python

"""
Heartbeat server/client to detect soft lockups
"""

import socket, os, sys, time, getopt

def daemonize(output_file):
    try:
        pid = os.fork()
    except OSError, e:
        raise Exception, "error %d: %s" % (e.strerror, e.errno)

    if pid:
        os._exit(0)

    os.umask(0)
    os.setsid()
    sys.stdout.flush()
    sys.stderr.flush()

    if file:
        output_handle = file(output_file, 'a+', 0)
        # autoflush stdout/stderr
        sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', 0)
        sys.stderr = os.fdopen(sys.stderr.fileno(), 'w', 0)
    else:
        output_handle = file('/dev/null', 'a+')

    stdin_handle = open('/dev/null', 'r')
    os.dup2(output_handle.fileno(), sys.stdout.fileno())
    os.dup2(output_handle.fileno(), sys.stderr.fileno())
    os.dup2(stdin_handle.fileno(), sys.stdin.fileno())

def recv_all(sock):
    total_data = []
    while True:
        data = sock.recv(1024)
        if not data:
            break
        total_data.append(data)
    return ''.join(total_data)

def run_server(host, port, daemon, file, queue_size, threshold, drift):
    if daemon:
        daemonize(output_file=file)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind((host, port))
    sock.listen(queue_size)
    timeout_interval = threshold * 2
    prev_check_timestamp = float(time.time())
    while 1:
        c_sock, c_addr = sock.accept()
        heartbeat = recv_all(c_sock)
        local_timestamp = float(time.time())
        drift = check_heartbeat(heartbeat, local_timestamp, threshold, check_drift)
        # NOTE: this doesn't work if the only client is the one that timed
        # out, but anything more complete would require another thread and
        # a lock for client_prev_timestamp.
        if local_timestamp - prev_check_timestamp > threshold * 2.0:
            check_for_timeouts(threshold, check_drift)
            prev_check_timestamp = local_timestamp
        if verbose:
            if check_drift:
                print "%.2f: %s (%s)" % (local_timestamp, heartbeat, drift)
            else:
                print "%.2f: %s" % (local_timestamp, heartbeat)

def run_client(host, port, daemon, file, interval):
    if daemon:
        daemonize(output_file=file)
    seq = 1
    while 1:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((host, port))
            heartbeat = get_heartbeat(seq)
            sock.sendall(heartbeat)
            sock.close()
            if verbose:
                print heartbeat
        except socket.error, (value, message):
            print "%.2f: ERROR, %d - %s" % (float(time.time()), value, message)

        seq += 1
        time.sleep(interval)

def get_heartbeat(seq=1):
    return "%s %06d %.2f" % (hostname, seq, float(time.time()))

def check_heartbeat(heartbeat, local_timestamp, threshold, check_drift):
    hostname, seq, timestamp = heartbeat.rsplit()
    timestamp = float(timestamp)
    if client_prev_timestamp.has_key(hostname):
        delta = local_timestamp - client_prev_timestamp[hostname]
        if delta > threshold:
            print "%.2f: ALERT, SLU detected on host %s, delta %ds" \
                % (float(time.time()), hostname, delta)

    client_prev_timestamp[hostname] = local_timestamp

    if check_drift:
        if not client_clock_offset.has_key(hostname):
            client_clock_offset[hostname] = timestamp - local_timestamp
            client_prev_drift[hostname] = 0
        drift = timestamp - local_timestamp - client_clock_offset[hostname]
        drift_delta = drift - client_prev_drift[hostname]
        client_prev_drift[hostname] = drift
        return "drift %+4.2f (%+4.2f)" % (drift, drift_delta)

def check_for_timeouts(threshold, check_drift):
    local_timestamp = float(time.time())
    hostname_list = list(client_prev_timestamp)
    for hostname in hostname_list:
        timestamp = client_prev_timestamp[hostname]
        delta = local_timestamp - timestamp
        if delta > threshold * 2:
            print "%.2f: ALERT, SLU detected on host %s, no heartbeat for %ds" \
                % (local_timestamp, hostname, delta)
            del client_prev_timestamp[hostname]
            if check_drift:
                del client_clock_offset[hostname]
                del client_prev_drift[hostname]

def usage():
    print """
Usage:

    heartbeat_slu.py --server --address <bind_address> --port <bind_port>
                     [--file <output_file>] [--no-daemon] [--verbose]
                     [--threshold <heartbeat threshold>]

    heartbeat_slu.py --client --address <server_address> -p <server_port>
                     [--file output_file] [--no-daemon] [--verbose]
                     [--interval <heartbeat interval in seconds>]
"""

# host information and global data
hostname = socket.gethostname()
client_prev_timestamp = {}
client_clock_offset = {}
client_prev_drift = {}

# default param values
host_port = 9001
host_address = ''
interval = 1 # seconds between heartbeats
threshold = 10 # seconds late till alert
is_server = False
is_daemon = True
file_server = "/tmp/heartbeat_server.out"
file_client = "/tmp/heartbeat_client.out"
file_selected = None
queue_size = 5
verbose = False
check_drift = False

# process cmdline opts
try:
    opts, args = getopt.getopt(sys.argv[1:], "vhsfd:p:a:i:t:", [
                    "server", "client", "no-daemon", "address=", "port=",
                    "file=", "server", "interval=", "threshold=", "verbose",
                    "check-drift", "help"])
except getopt.GetoptError, e:
    print "error: %s" % str(e)
    usage()
    exit(1)

for param, value in opts:
    if param in ["-p", "--port"]:
        host_port = int(value)
    elif param in ["-a", "--address"]:
        host_address = value
    elif param in ["-s", "--server"]:
        is_server = True
    elif param in ["-c", "--client"]:
        is_server = False
    elif param in ["--no-daemon"]:
        is_daemon = False
    elif param in ["-f", "--file"]:
        file_selected = value
    elif param in ["-i", "--interval"]:
        interval = int(value)
    elif param in ["-t", "--threshold"]:
        threshold = int(value)
    elif param in ["-d", "--check-drift"]:
        check_drift = True
    elif param in ["-v", "--verbose"]:
        verbose = True
    elif param in ["-h", "--help"]:
        usage()
        exit(0)
    else:
        print "error: unrecognized option: %s" % value
        usage()
        exit(1)

# run until we're terminated
if is_server:
    file_server = file_selected or file_server
    run_server(host_address, host_port, is_daemon, file_server, queue_size, threshold, check_drift)
else:
    file_client = file_selected or file_client
    run_client(host_address, host_port, is_daemon, file_client, interval)
