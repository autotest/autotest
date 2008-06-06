import collections
import common
from autotest_lib.client.common_lib import logging


class status_stack(object):
    statuses = logging.job_statuses


    def __init__(self):
        self.status_stack = [self.statuses[-1]]


    def current_status(self):
        return self.status_stack[-1]


    def update(self, new_status):
        if new_status not in self.statuses:
            return
        old = self.statuses.index(self.current_status())
        new = self.statuses.index(new_status)
        if new < old:
            self.status_stack[-1] = new_status


    def start(self):
        self.status_stack.append(self.statuses[-1])


    def end(self):
        result = self.status_stack.pop()
        if len(self.status_stack) == 0:
            self.status_stack.append(self.statuses[-1])
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
