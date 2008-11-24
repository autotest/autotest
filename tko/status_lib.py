import collections, re
import common
from autotest_lib.client.common_lib import log


statuses = log.job_statuses


def is_worse_than(lhs, rhs):
    """ Compare two statuses and return a boolean indicating if the LHS status
    is worse than the RHS status."""
    return (statuses.index(lhs) < statuses.index(rhs))


def is_worse_than_or_equal_to(lhs, rhs):
    """ Compare two statuses and return a boolean indicating if the LHS status
    is worse than or equal to the RHS status."""
    if lhs == rhs:
        return True
    return is_worse_than(lhs, rhs)


DEFAULT_BLACKLIST = ('\r\x00',)
def clean_raw_line(raw_line, blacklist=DEFAULT_BLACKLIST):
    """Strip blacklisted characters from raw_line."""
    return re.sub('|'.join(blacklist), '', raw_line)


class status_stack(object):
    def __init__(self):
        self.status_stack = [statuses[-1]]


    def current_status(self):
        return self.status_stack[-1]


    def update(self, new_status):
        if new_status not in statuses:
            return
        if is_worse_than(new_status, self.current_status()):
            self.status_stack[-1] = new_status


    def start(self):
        self.status_stack.append(statuses[-1])


    def end(self):
        result = self.status_stack.pop()
        if len(self.status_stack) == 0:
            self.status_stack.append(statuses[-1])
        return result


    def size(self):
        return len(self.status_stack) - 1


class line_buffer(object):
    def __init__(self):
        self.buffer = collections.deque()


    def get(self):
        return self.buffer.pop()


    def put(self, line):
        self.buffer.appendleft(line)


    def put_multiple(self, lines):
        self.buffer.extendleft(lines)


    def put_back(self, line):
        self.buffer.append(line)


    def size(self):
        return len(self.buffer)


def parser(version):
    library = "autotest_lib.tko.parsers.version_%d" % version
    module = __import__(library, globals(), locals(), ["parser"])
    return module.parser()
