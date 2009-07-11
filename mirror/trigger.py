import os, re

# Given a file full of rsync output, scan through it for things that look like
# legitimate releases. Return the simplified triggers for each of those files.

matches = (
        # The major tarballs
        r'linux-(2\.6\.\d+)\.tar\.bz2',
        # Stable releases
        r'patch-(2\.6\.\d+\.\d+)\.bz2',
        # -rc releases
        r'patch-(2\.6\.\d+-rc\d+)\.bz2',
        # -git releases
        r'patch-(2\.6\.\d+(-rc\d+)?-git\d+).bz2',
        # -mm tree
        r'(2\.6\.\d+(-rc\d+)?-mm\d+)\.bz2',
          )

compiled_matches = [re.compile(r) for r in matches]


class Trigger(object):
    def __init__(self):
        self.__actions = []

    def __re_scan(self, pattern, line):
        """
        First check to see whether the pattern matches.
                (eg. Does it match "linux-2.6.\d.tar.bz2" ?)
                Then we strip out the actual trigger itself from that,
                and return it.
                (eg. return "2.6.\d")
                Note that the pattern uses match,
                so you need the whole filename
        """
        match = pattern.match(line)
        if match:
            return match.group(1)
        else:
            return None


    def scan(self, input_file):
        triggers = []
        for line in open(input_file, 'r').readlines():
            for pattern in compiled_matches:
                filename = os.path.basename(line)
                t = self.__re_scan(pattern, filename)
                if t:
                    triggers.append(t)

        # Call each of the actions and pass in the kernel list
        for action in self.__actions:
            action(triggers)


    def add_action(self, func):
        self.__actions.append(func)
