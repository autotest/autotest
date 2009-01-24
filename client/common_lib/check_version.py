# This file must use Python 1.5 syntax.
import sys, string, os, glob, re


def extract_version(path):
    match = re.search(r'/python(\d+)\.(\d+)$', path)
    if match:
        return (int(match.group(1)), int(match.group(2)))
    else:
        return None


def find_desired_python():
    """Returns the path of the desired python interpreter."""
    pythons = []
    pythons.extend(glob.glob('/usr/bin/python2*'))
    pythons.extend(glob.glob('/usr/local/bin/python2*'))

    possible_versions = []
    best_python = (0, 0), ''
    for python in pythons:
        version = extract_version(python)
        if version >= (2, 4):
            possible_versions.append((version, python))

    possible_versions.sort()

    if not possible_versions:
        raise ValueError('Python 2.x version 2.4 or better is required')
    # Return the lowest possible version so that we use 2.4 if available
    # rather than more recent versions.
    return possible_versions[0][1]


def restart():
    python = find_desired_python()
    sys.stderr.write('NOTE: %s switching to %s\n' %
                     (os.path.basename(sys.argv[0]), python))
    sys.argv.insert(0, '-u')
    sys.argv.insert(0, python)
    os.execv(sys.argv[0], sys.argv)


def check_python_version():
    version = None
    try:
        version = sys.version_info[0:2]
    except AttributeError:
        pass # pre 2.0, no neat way to get the exact number

    # The change to prefer 2.4 really messes up any systems which have both
    # the new and old version of Python, but where the newer is default.
    # This is because packages, libraries, etc are all installed into the
    # new one by default. Some things (like running under mod_python) just
    # plain don't handle python restarting properly. I know that I do some
    # development under ipython and whenever I run (or do anything that
    # runs) 'import common' it restarts my shell. Overall, the change was
    # fairly annoying for me (and I can't get around having 2.4 and 2.5
    # installed with 2.5 being default).
    if not version or version < (2, 4) or version >= (3, 0):
        try:
            # We can't restart when running under mod_python.
            from mod_python import apache
        except ImportError:
            restart()
