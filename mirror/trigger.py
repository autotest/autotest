#!/usr/bin/python2.4
import os, re

# Given a file full of rsync output, scan through it for things that look like
# legitimate releases. Return the simplified triggers for each of those files.

matches = (
       	# The major tarballs
	(re.compile(r'linux-2\.6\.\d+\.tar\.bz2'),
	 re.compile(r'2\.6\.\d+') ),
       	# Stable releases
	(re.compile(r'patch-2\.6\.\d+\.\d+\.bz2'),
	 re.compile(r'2\.6\.\d+') ),
        # -rc releases
	(re.compile(r'patch-2\.6\.\d+-rc\d+\.bz2'),
	 re.compile(r'2.6.\d+-rc\d+') ),
        # -git releases
        (re.compile(r'patch-2\.6\.\d+(-rc\d+)?-git\d+.bz2'),
	 re.compile(r'2.6.\d+(-rc\d+)?-git\d+') ),
	# -mm tree
	(re.compile(r'2\.6\.\d+(-rc\d+)?-mm\d+\.bz2'),
	 re.compile(r'2\.6\.\d+(-rc\d+)?-mm\d+') ),
	  )

def re_scan(pattern1, pattern2, line):
	"""
	Bi-stage match routine. 

	First check to see whether the first string matches.
			(eg. Does it match "linux-2.6.\d.tar.bz2" ?)
	Then we strip out the actual trigger itself from that, and return it.
			(eg. return "2.6.\d")

	Note that the first string uses match, so you need the whole filename
	"""
	match1 = pattern1.match(line)
	if not match1:
		return None
	match2 = pattern2.search(match1.group())
	if not match2:
		return None
	return match2.group()

	
def scan(input_file):
	triggers = []
	for line in open(input_file, 'r').readlines():
		for match in matches:
			file = os.path.basename(line)
			t = re_scan(match[0], match[1], file)
			if t:
				triggers.append(t)
	return triggers

