#!/usr/bin/python
import sys, re


_status_list = ["GOOD", "WARN", "FAIL", "ABORT", "ERROR"]
_order_dict = {None: -1}
_order_dict.update((status, i)
		   for i, status in enumerate(_status_list))
_status_regex = re.compile(r"(?:STATUS\s*)?(%s)\s*(.*)" % "|".join(_status_list))


def _worst_status(old_status, new_status):
	if _order_dict[new_status] > _order_dict[old_status]:
		return new_status
	else:
		return old_status

def _update_details(status, details):
	if details == "----\trun starting":
		return "Running test"
	elif details == "----\treboot":
		if _worst_status("GOOD", status) == "GOOD":
			return "Rebooting"
		else:
			return "Reboot failed - machine dead"
	# if we don't have a better message, just use the raw details
	return details


def parse_status(status_log):
	"""
	Parses a status.log file and returns a list of meaningful results.
	"""
	counts = dict((status, 0) for status in _status_list)
	current_status = None
	details = ""
	for line in file(status_log):
		line = line.rstrip()
		status_match = _status_regex.match(line)
		if status_match:
			new_status, details = status_match.groups()
			current_status = _worst_status(current_status, new_status)
			details = _update_details(current_status, details)
		elif line == "DONE":
			details = "Between tests"
			counts[current_status] += 1
			current_status = None
		else:
			details = line
	results = [details]
	results += ["%d %s" % (counts[status], status) for status in _status_list]
	return results


if __name__ == "__main__":
 	args = sys.argv[1:]
 	if len(args) != 1:
 		print "USAGE: status.py status_log"
 		sys.exit(1)
 	for result in parse_status(args[0]):
		print result
