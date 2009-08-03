# Shared utility functions across monitors scripts.

import fcntl, os, re, select, signal, subprocess, sys, time

TERM_MSG = 'Console connection unexpectedly lost. Terminating monitor.'


class Error(Exception):
    pass


class InvalidTimestampFormat(Error):
    pass


def prepend_timestamp(msg, format):
    """Prepend timestamp to a message in a standard way.

    Args:
      msg: str; Message to prepend timestamp to.
      format: str or callable; Either format string that
          can be passed to time.strftime or a callable
          that will generate the timestamp string.

    Returns: str; 'timestamp\tmsg'
    """
    if type(format) is str:
        timestamp = time.strftime(format, time.localtime())
    elif callable(format):
        timestamp = str(format())
    else:
        raise InvalidTimestampFormat

    return '%s\t%s' % (timestamp, msg)


def write_logline(logfile, msg, timestamp_format=None):
    """Write msg, possibly prepended with a timestamp, as a terminated line.

    Args:
      logfile: file; File object to .write() msg to.
      msg: str; Message to write.
      timestamp_format: str or callable; If specified will
          be passed into prepend_timestamp along with msg.
    """
    msg = msg.rstrip('\n')
    if timestamp_format:
        msg = prepend_timestamp(msg, timestamp_format)
    logfile.write(msg + '\n')


def make_alert(warnfile, msg_type, msg_template, timestamp_format=None):
    """Create an alert generation function that writes to warnfile.

    Args:
      warnfile: file; File object to write msg's to.
      msg_type: str; String describing the message type
      msg_template: str; String template that function params
          are passed through.
      timestamp_format: str or callable; If specified will
          be passed into prepend_timestamp along with msg.

    Returns: function with a signature of (*params);
        The format for a warning used here is:
            %(timestamp)d\t%(msg_type)s\t%(status)s\n
    """
    if timestamp_format is None:
        timestamp_format = lambda: int(time.time())

    def alert(*params):
        formatted_msg = msg_type + "\t" + msg_template % params
        timestamped_msg = prepend_timestamp(formatted_msg, timestamp_format)
        print >> warnfile, timestamped_msg
    return alert


def build_alert_hooks(patterns_file, warnfile):
    """Parse data in patterns file and transform into alert_hook list.

    Args:
      patterns_file: file; File to read alert pattern definitions from.
      warnfile: file; File to configure alert function to write warning to.

    Returns:
      list; Regex to alert function mapping.
          [(regex, alert_function), ...]
    """
    pattern_lines = patterns_file.readlines()
    # expected pattern format:
    # <msgtype> <newline> <regex> <newline> <alert> <newline> <newline>
    #   msgtype = a string categorizing the type of the message - used for
    #             enabling/disabling specific categories of warnings
    #   regex   = a python regular expression
    #   alert   = a string describing the alert message
    #             if the regex matches the line, this displayed warning will
    #             be the result of (alert % match.groups())
    patterns = zip(pattern_lines[0::4], pattern_lines[1::4],
                   pattern_lines[2::4])

    # assert that the patterns are separated by empty lines
    if sum(len(line.strip()) for line in pattern_lines[3::4]) > 0:
        raise ValueError('warning patterns are not separated by blank lines')

    hooks = []
    for msgtype, regex, alert in patterns:
        regex = re.compile(regex.rstrip('\n'))
        alert_function = make_alert(warnfile, msgtype.rstrip('\n'),
                                    alert.rstrip('\n'))
        hooks.append((regex, alert_function))
    return hooks


def process_input(
    input, logfile, log_timestamp_format=None, alert_hooks=()):
    """Continuously read lines from input stream and:

    - Write them to log, possibly prefixed by timestamp.
    - Watch for alert patterns.

    Args:
      input: file; Stream to read from.
      logfile: file; Log file to write to
      log_timestamp_format: str; Format to use for timestamping entries.
          No timestamp is added if None.
      alert_hooks: list; Generated from build_alert_hooks.
          [(regex, alert_function), ...]
    """
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
    """Retrieve last lines seen for path.

    Open corresponding lastline file for path
    If there isn't one or isn't a match return None

    Args:
      lastlines_dirpath: str; Dirpath to store lastlines files to.
      path: str; Filepath to source file that lastlines came from.

    Returns:
      str; Last lines seen if they exist
      - Or -
      None; Otherwise
    """
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
    """Write data to lastlines file for path.

    Args:
      lastlines_dirpath: str; Dirpath to store lastlines files to.
      path: str; Filepath to source file that data comes from.
      data: str;

    Returns:
      str; Filepath that lastline data was written to.
    """
    underscored = path.replace('/', '_')
    dest_path = os.path.join(lastlines_dirpath, underscored)
    open(dest_path, 'w').write(data)
    return dest_path


def nonblocking(pipe):
    """Set python file object to nonblocking mode.

    This allows us to take advantage of pipe.read()
    where we don't have to specify a buflen.
    Cuts down on a few lines we'd have to maintain.

    Args:
      pipe: file; File object to modify

    Returns: pipe
    """
    flags = fcntl.fcntl(pipe, fcntl.F_GETFL)
    fcntl.fcntl(pipe, fcntl.F_SETFL, flags| os.O_NONBLOCK)
    return pipe


def launch_tails(follow_paths, lastlines_dirpath=None):
    """Launch a tail process for each follow_path.

    Args:
      follow_paths: list;
      lastlines_dirpath: str;

    Returns:
      tuple; (procs, pipes) or
          ({path: subprocess.Popen, ...}, {file: path, ...})
    """
    if lastlines_dirpath and not os.path.exists(lastlines_dirpath):
        os.makedirs(lastlines_dirpath)

    tail_cmd = ('/usr/bin/tail', '--retry', '--follow=name')
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
    """Wait on tail pipes for new data for waitsecs, return any new lines.

    Args:
      pipes: dict; {subprocess.Popen: follow_path, ...}
      lastlines_dirpath: str; Path to write lastlines to.
      waitsecs: int; Timeout to pass to select

    Returns:
      tuple; (lines, bad_pipes) or ([line, ...], [subprocess.Popen, ...])
    """
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
    """Helper for killing off remaining live subprocesses.

    Args:
      subprocs: list; [subprocess.Popen, ...]
    """
    for proc in subprocs:
        if proc.poll() is None:
            os.kill(proc.pid, signal.SIGKILL)
            proc.wait()


def follow_files(follow_paths, outstream, lastlines_dirpath=None, waitsecs=5):
    """Launch tail on a set of files and merge their output into outstream.

    Args:
      follow_paths: list; Local paths to launch tail on.
      outstream: file; Output stream to write aggregated lines to.
      lastlines_dirpath: Local dirpath to record last lines seen in.
      waitsecs: int; Timeout for poll_tail_pipes.
    """
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
