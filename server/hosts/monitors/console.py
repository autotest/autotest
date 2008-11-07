# Script for translating console output (from STDIN) into Autotest
# warning messages.
#
# Usage:
#    python console.py <logfile_name> <warn_fd>
#
#    logfile_name - a filename to log all console output to
#    warn_fd - a file descriptor that warning messages can be written to


import sys, re, os, time

log_timestamp_format = '[%Y-%m-%d %H:%M:%S]'
logfile = open(sys.argv[1], 'a', 0)
warnfile = os.fdopen(int(sys.argv[2]), 'w', 0)


def prepend_timestamp(msg, format=None):
    if not format:
        timestamp = str(int(time.time()))
    else:
        timestamp = time.strftime(format, time.localtime())
    return "%s\t%s" % (timestamp, msg)


def write_logline(msg):
    timestamped_msg = prepend_timestamp(msg.rstrip(), log_timestamp_format)
    logfile.write(timestamped_msg + '\n')


# the format for a warning used here is:
#   <timestamp (integer)> <tab> <status (string)> <newline>
def make_alert(msg):
    def alert(*params):
        formatted_msg = msg % params
        timestamped_msg = prepend_timestamp(formatted_msg)
        print >> warnfile, timestamped_msg
    return alert


pattern_file = os.path.join(os.path.dirname(__file__), 'console_patterns')
pattern_lines = open(pattern_file).readlines()

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

hooks = [(re.compile(regex.rstrip('\n')), make_alert(alert.rstrip('\n')))
         for regex, alert in patterns]

while True:
    line = sys.stdin.readline()
    if len(line) == 0:
        # this should only happen if the remote console unexpectedly goes away
        # terminate this process so that we don't spin forever doing 0-length
        # reads off of stdin
        write_logline(
            'Console connection unexpectedly lost. Terminating monitor.')

        break

    write_logline(line)

    for regex, callback in hooks:
        match = re.match(regex, line.strip())
        if match:
            callback(*match.groups())
