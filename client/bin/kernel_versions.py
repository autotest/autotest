#
# kernel_versions.py -- linux kernel version comparisons
#
__author__ = """Copyright Andy Whitcroft 2007"""

import sys,re

# 
# Sort key for ordering versions chronologically.  The key ordering
# problem is between that introduced by -rcN.  These come _before_
# their accompanying version.
# 
#   2.6.0 -> 2.6.1-rc1 -> 2.6.1
# 
# In order to sort them we convert all non-rc releases to a pseudo
# -rc99 release.  We also convert all numbers to two digits.  The
# result is then sortable textually.
# 
#   02.06.00-rc99 -> 02.06.01-rc01 -> 02.06.01-rc99
# 
encode_sep = re.compile('(\D+)')
def version_encode(version):
	bits = encode_sep.split(version)
	if len(bits) < 6 or bits[5] != '-rc':
		bits.insert(5, '99')
		bits.insert(5, '-rc')
	for n in range(0, len(bits), 2):
		if len(bits[n]) < 2:
			bits[n] = '0' + bits[n]

	return ''.join(bits)


def version_limit(version, n):
	bits = encode_sep.split(version)
	return ''.join(bits[0:n])


def version_len(version):
	return len(encode_sep.split(version))

#
# Given a list of versions find the nearest version which is deemed
# less than or equal to the target.  Versions are in linux order
# as follows:
# 
#   2.6.0 -> 2.6.1 -> 2.6.2-rc1 -> 2.6.2-rc2 -> 2.6.2 -> 2.6.3-rc1
#              |        |\
#              |        | 2.6.2-rc1-mm1 -> 2.6.2-rc1-mm2
#              |        \
#              |         2.6.2-rc1-ac1 -> 2.6.2-rc1-ac2
#              \   
#               2.6.1-mm1 -> 2.6.1-mm2
# 
# Note that a 2.6.1-mm1 is not a predecessor of 2.6.2-rc1-mm1.
#
def version_choose_config(version, candidates):
	# Check if we have an exact match ... if so magic
	if version in candidates:
		return version

	# Sort the search key into the list ordered by 'age'
	deco = [ (version_encode(v), i, v) for i, v in
					enumerate(candidates + [ version ]) ]
	deco.sort()
	versions = [ v for _, _, v in deco ]

	# Everything sorted below us is of interst.
	for n in range(len(versions) - 1, -1, -1):
		if versions[n] == version:
			break
	n -= 1

	# Try ever shorter 'prefixes' 2.6.20-rc3-mm, 2.6.20-rc, 2.6. etc
	# to match against the ordered list newest to oldest.
	length = version_len(version) - 1
	version = version_limit(version, length)
	while length > 1:
		for o in range(n, -1, -1):
			if version_len(versions[o]) == (length + 1) and \
			   version_limit(versions[o], length) == version:
				return versions[o]
		length -= 2
		version = version_limit(version, length)

	return None
