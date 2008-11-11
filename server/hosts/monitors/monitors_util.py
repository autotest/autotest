# Shared utility functions across monitors scripts.

import fcntl, os, re, select, signal, subprocess, sys, time

TERM_MSG = 'Console connection unexpectedly lost. Terminating monitor.'


class Error(Exception):
    pass


class InvalidTimestampFormat(Error):
    pass


def prepend_timestamp(msg, format):
    if type(format) is str:
        timestamp = time.strftime(format, time.localtime())
    elif callable(format):
        timestamp = str(format())
    else:
      raise InvalidTimestampFormat

    return '%s\t%s' % (timestamp, msg)


def write_logline(logfile, msg, timestamp_format=None):
    msg = msg.rstrip()
    if timestamp_format:
      msg = prepend_timestamp(msg, timestamp_format)
    logfile.write(msg + '\n')


# the format for a warning used here is:
#   <timestamp (integer)> <tab> <status (string)> <newline>
def make_alert(warnfile, msg_template, timestamp_format=None):
    if timestamp_format is None:
        timestamp_format = lambda: int(time.time())

    def alert(*params):
        formatted_msg = msg_template % params
        timestamped_msg = prepend_timestamp(formatted_msg, timestamp_format)
        print >> warnfile, timestamped_msg
    return alert


def build_alert_hooks(patterns_file, warnfile):
    pattern_lines = patterns_file.readlines()
    # expected pattern format:
    # <regex> <newline> <alert> <newline> <newline>
    #   regex = a python regular expression
    #   alert = a string describing the alert message
    #           if the regex matches the line, this displayed warning will
    #           be the result of (alert % match.groups())
    patterns = zip(pattern_lines[0::3], pattern_lines[1::3])

    # assert that the patterns are separated by empty lines
    if sum(len(line.strip()) for line in pattern_lines[2::3]) > 0:
        raise ValueError('warning patterns are not separated by blank lines')

    hooks = [
        (re.compile(regex.rstrip('\n')),
         make_alert(warnfile, alert.rstrip('\n')))
        for regex, alert in patterns]
    return hooks


def process_input(
    input, logfile, log_timestamp_format=None, alert_hooks=()):
    while True:
        line = input.readline()
        if len(line) == 0:
            # this should only happen if the remote console unexpectedly
            # goes away. terminate this process so that we don't spin
            # forever doing 0-length reads off of input
            write_logline(logfile, TERM_MSG, log_timestamp_format)
            break

        if line == '\n':
            # If it's just an empty line we discard and continue.
            continue

        write_logline(logfile, line, log_timestamp_format)

        for regex, callback in alert_hooks:
            match = re.match(regex, line.strip())
            if match:
                callback(*match.groups())


def lookup_lastlines(lastlines_dirpath, path):
    # Open corresponding lastline file for path
    # If there isn't one or isn't a match return None
    underscored = path.replace('/', '_')
    try:
        lastlines_file = open(os.path.join(lastlines_dirpath, underscored))
    except (OSError, IOError):
        return

    lastlines = lastlines_file.read()
    lastlines_file.close()
    os.remove(lastlines_file.name)
    if not lastlines:
        return

    try:
        target_file = open(path)
    except (OSError, IOError):
        return

    # Load it all in for now
    target_data = target_file.read()
    target_file.close()
    # Get start loc in the target_data string, scanning from right
    loc = target_data.rfind(lastlines)
    if loc == -1:
        return

    # Then translate this into a reverse line number
    # (count newlines that occur afterward)
    reverse_lineno = target_data.count('\n', loc + len(lastlines))
    return reverse_lineno


def write_lastlines_file(lastlines_dirpath, path, data):
    underscored = path.replace('/', '_')
    dest_path = os.path.join(lastlines_dirpath, underscored)
    open(dest_path, 'w').write(data)
    return dest_path


def nonblocking(pipe):
    # This allows us to take advantage of pipe.read()
    # where we don't have to specify a buflen.
    # Cuts down on a few lines we'd have to maintain.
    flags = fcntl.fcntl(pipe, fcntl.F_GETFL)
    fcntl.fcntl(pipe, fcntl.F_SETFL, flags| os.O_NONBLOCK)
    return pipe


def launch_tails(follow_paths, lastlines_dirpath=None):
    if lastlines_dirpath and not os.path.exists(lastlines_dirpath):
        os.makedirs(lastlines_dirpath)

    tail_cmd = ('/usr/bin/tail', '--retry', '--follow=name')
    # Launch a tail process for each
    procs = {}  # path -> tail_proc
    pipes = {}  # tail_proc.stdout -> path
    for path in follow_paths:
        cmd = list(tail_cmd)
        if lastlines_dirpath:
            reverse_lineno = lookup_lastlines(lastlines_dirpath, path)
            if reverse_lineno is None:
                reverse_lineno = 1
            cmd.append('--lines=%d' % reverse_lineno)

        cmd.append(path)
        tail_proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        procs[path] = tail_proc
        pipes[nonblocking(tail_proc.stdout)] = path

    return procs, pipes


def poll_tail_pipes(pipes, lastlines_dirpath=None, waitsecs=5):
    lines = []
    bad_pipes = []
    # Block until at least one is ready to read or waitsecs elapses
    ready, _, _ = select.select(pipes.keys(), (), (), waitsecs)
    for fi in ready:
        path = pipes[fi]
        data = fi.read()
        if len(data) == 0:
            # If no data, process is probably dead, add to bad_pipes
            bad_pipes.append(fi)
            continue

        if lastlines_dirpath:
            # Overwrite the lastlines file for this source path
            # Probably just want to write the last 1-3 lines.
            write_lastlines_file(lastlines_dirpath, path, data)

        for line in data.splitlines():
            lines.append('[%s]\t%s\n' % (path, line))

    return lines, bad_pipes


def snuff(subprocs):
    for proc in subprocs:
        if proc.poll() is None:
            os.kill(proc.pid, signal.SIGKILL)
            proc.wait()


def follow_files(follow_paths, outstream, lastlines_dirpath=None, waitsecs=5):
    procs, pipes = launch_tails(follow_paths, lastlines_dirpath)
    while pipes:
        lines, bad_pipes = poll_tail_pipes(pipes, lastlines_dirpath, waitsecs)
        for bad in bad_pipes:
            pipes.pop(bad)

        try:
            outstream.writelines(['\n'] + lines)
            outstream.flush()
        except (IOError, OSError), e:
            # Something is wrong. Stop looping.
            break

    snuff(procs.values())
