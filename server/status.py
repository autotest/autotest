#!/usr/bin/python
import sys, re


_status_regex = re.compile(r"STATUS\s*(GOOD|WARN|FAIL)\s*(.*)")

def _determine_status(old_status, new_status):
	order = {None: -1, "GOOD": 0, "WARN": 1, "FAIL": 2}
	if order[new_status] > order[old_status]:
		return new_status
	else:
		return old_status


def parse_status(status_log):
	"""
	Parses a status.log file and returns a list of meaningful results.
	"""
	counts = {"GOOD": 0, "WARN": 0, "FAIL": 0}
	status = None
	details = ""
	for line in file(status_log):
		line = line.rstrip()
		status_match = _status_regex.match(line)
		if status_match:
			new_status, details = status_match.groups()
			status = _determine_status(status, new_status)
			if details == "----\trun starting":
				details = "Running test"
		elif line == "DONE":
			details = "Between tests"
			counts[status] += 1
			status = None
		elif line == "REBOOT":
			details = "Rebooting"
		elif line == "REBOOT ERROR":
			details = "Machine was unable to reboot"
		else:
			details = line
	results = []
	results.append(details)
	results.append("%d GOOD" % counts["GOOD"])
	results.append("%d WARN" % counts["WARN"])
	results.append("%d FAIL" % counts["FAIL"])
	return results


if __name__ == "__main__":
 	args = sys.argv[1:]
 	if len(args) != 1:
 		print "USAGE: status.py status_log"
 		sys.exit(1)
 	for result in parse_status(args[0]):
		print result
