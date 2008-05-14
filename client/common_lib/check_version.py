import sys, string, os, glob, re


def extract_version(path):
	match = re.search(r'/python(\d+)\.(\d+)$', path)
	if match:
		return (int(match.group(1)), int(match.group(2)))
	else:
		return None


def find_newest_python():
	pythons = []
	pythons.extend(glob.glob('/usr/bin/python*'))
	pythons.extend(glob.glob('/usr/local/bin/python*'))

	best_python = (0, 0), ''
	for python in pythons:
		version = extract_version(python)
		if version > best_python[0] and version >= (2, 4):
			best_python = version, python

	if best_python[0] == (0, 0):
		raise ValueError('Python 2.4 or newer is needed')
	return best_python[1]
	

def restart():
	python = find_newest_python()
	sys.argv.insert(0, '-u')
	sys.argv.insert(0, python)
	os.execv(sys.argv[0], sys.argv)


def check_python_version():
	version = None
	try:
		version = sys.version_info[0:2]
	except AttributeError:
		pass # pre 2.0, no neat way to get the exact number
	if not version or version < (2, 4):
		restart()
