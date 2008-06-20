"""
The main job wrapper for the server side.

This is the core infrastructure. Derived from the client side job.py

Copyright Martin J. Bligh, Andy Whitcroft 2007
"""

__author__ = """
Martin J. Bligh <mbligh@google.com>
Andy Whitcroft <apw@shadowen.org>
"""

import re, sys
from autotest_lib.server import base_server_job

# a file-like object for catching stderr from an autotest client and
# extracting status logs from it
class client_logger(object):
    """Partial file object to write to both stdout and
    the status log file.  We only implement those methods
    utils.run() actually calls.
    """
    parser = re.compile(r"^AUTOTEST_STATUS:([^:]*):(.*)$")
    extract_indent = re.compile(r"^(\t*).*$")

    def __init__(self, job):
        self.job = job
        self.leftover = ""
        self.last_line = ""
        self.logs = {}


    def _process_log_dict(self, log_dict):
        log_list = log_dict.pop("logs", [])
        for key in sorted(log_dict.iterkeys()):
            log_list += self._process_log_dict(log_dict.pop(key))
        return log_list


    def _process_logs(self):
        """Go through the accumulated logs in self.log and print them
        out to stdout and the status log. Note that this processes
        logs in an ordering where:

        1) logs to different tags are never interleaved
        2) logs to x.y come before logs to x.y.z for all z
        3) logs to x.y come before x.z whenever y < z

        Note that this will in general not be the same as the
        chronological ordering of the logs. However, if a chronological
        ordering is desired that one can be reconstructed from the
        status log by looking at timestamp lines."""
        log_list = self._process_log_dict(self.logs)
        for line in log_list:
            self.job._record_prerendered(line + '\n')
        if log_list:
            self.last_line = log_list[-1]


    def _process_quoted_line(self, tag, line):
        """Process a line quoted with an AUTOTEST_STATUS flag. If the
        tag is blank then we want to push out all the data we've been
        building up in self.logs, and then the newest line. If the
        tag is not blank, then push the line into the logs for handling
        later."""
        print line
        if tag == "":
            self._process_logs()
            self.job._record_prerendered(line + '\n')
            self.last_line = line
        else:
            tag_parts = [int(x) for x in tag.split(".")]
            log_dict = self.logs
            for part in tag_parts:
                log_dict = log_dict.setdefault(part, {})
            log_list = log_dict.setdefault("logs", [])
            log_list.append(line)


    def _process_line(self, line):
        """Write out a line of data to the appropriate stream. Status
        lines sent by autotest will be prepended with
        "AUTOTEST_STATUS", and all other lines are ssh error
        messages."""
        match = self.parser.search(line)
        if match:
            tag, line = match.groups()
            self._process_quoted_line(tag, line)
        else:
            print line


    def _format_warnings(self, last_line, warnings):
        # use the indentation of whatever the last log line was
        indent = self.extract_indent.match(last_line).group(1)
        # if the last line starts a new group, add an extra indent
        if last_line.lstrip('\t').startswith("START\t"):
            indent += '\t'
        return [self.job._render_record("WARN", None, None, msg,
                                        timestamp, indent).rstrip('\n')
                for timestamp, msg in warnings]


    def _process_warnings(self, last_line, log_dict, warnings):
        if log_dict.keys() in ([], ["logs"]):
            # there are no sub-jobs, just append the warnings here
            warnings = self._format_warnings(last_line, warnings)
            log_list = log_dict.setdefault("logs", [])
            log_list += warnings
            for warning in warnings:
                sys.stdout.write(warning + '\n')
        else:
            # there are sub-jobs, so put the warnings in there
            log_list = log_dict.get("logs", [])
            if log_list:
                last_line = log_list[-1]
            for key in sorted(log_dict.iterkeys()):
                if key != "logs":
                    self._process_warnings(last_line,
                                           log_dict[key],
                                           warnings)


    def write(self, data):
        # first check for any new console warnings
        warnings = self.job._read_warnings()
        self._process_warnings(self.last_line, self.logs, warnings)
        # now process the newest data written out
        data = self.leftover + data
        lines = data.split("\n")
        # process every line but the last one
        for line in lines[:-1]:
            self._process_line(line)
        # save the last line for later processing
        # since we may not have the whole line yet
        self.leftover = lines[-1]


    def flush(self):
        sys.stdout.flush()


    def close(self):
        if self.leftover:
            self._process_line(self.leftover)
        self._process_logs()
        self.flush()


# site_server_job.py may be non-existant or empty, make sure that an
# appropriate site_server_job class is created nevertheless
try:
    from autotest_lib.server.site_server_job import site_server_job
except ImportError:
    class site_server_job(base_server_job.base_server_job):
        pass

class server_job(site_server_job):
    pass
