#!/usr/bin/python
"""
Based on work from Douglas Creager <dcreager@dcreager.net>

Gets the current version number.  If possible, this is the
output of "git describe", modified to conform to the versioning
scheme that setuptools uses.  If "git describe" returns an error
(most likely because we're in an unpacked copy of a release tarball,
rather than in a git working copy), then we fall back on reading the
contents of the RELEASE-VERSION file.

To use this script, simply import it your setup.py file, and use the
results of get_version() as your package version:

from autotest.client.shared import version

setup(
    version=get_version(),
    .
    .
    .
)

This will automatically update the RELEASE-VERSION file, if
necessary.  Note that the RELEASE-VERSION file should *not* be
checked into git; please add it to your top-level .gitignore file.

You'll probably want to distribute the RELEASE-VERSION file in your
sdist tarballs; to do this, just create a MANIFEST.in file that
contains the following line:

include RELEASE-VERSION
"""
__all__ = ("get_version",)

import datetime
import os
import sys

try:
    import autotest.common as common  # pylint: disable=W0611
except ImportError:
    import common  # pylint: disable=W0611

from autotest.client import utils
from autotest.client.shared import error

_ROOT_PATH = os.path.join(sys.modules[__name__].__file__, "..", "..", "..")
_ROOT_PATH = os.path.abspath(_ROOT_PATH)

RELEASE_VERSION_PATH = os.path.join(_ROOT_PATH, 'RELEASE-VERSION')


def call_git_describe(abbrev=4):
    cwd = os.getcwd()
    os.chdir(_ROOT_PATH)
    try:
        try:
            command = 'git describe --abbrev=%d --always' % abbrev
            output = utils.system_output(command, verbose=False)
            # Since github won't host arbitray uploads anymore,
            # our new tags have to be prepended with autotest-
            # so we have prettier tarball names straight from
            # their system.
            if output.startswith("autotest-"):
                output = output.lstrip("autotest-")
            return output
        finally:
            os.chdir(cwd)
    except error.CmdError:
        return None


def read_release_version():
    try:
        f = open(RELEASE_VERSION_PATH, "r")
        try:
            version = f.readlines()[0]
            return version.strip()
        finally:
            f.close()
    except:
        return None


def write_release_version(version):
    f = open(RELEASE_VERSION_PATH, "w")
    f.write("%s\n" % version)
    f.close()


def get_version(abbrev=4):
    release_version = read_release_version()
    version = call_git_describe(abbrev)

    if version is None:
        version = release_version

    if version is None:
        now = datetime.datetime.now()
        version = "%s.%s.%s" % (now.year, now.month, now.day)

    if version != release_version:
        write_release_version(version)

    return version


if __name__ == "__main__":
    print get_version()
