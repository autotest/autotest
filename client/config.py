"""The Job Configuration

The job configuration, holding configuration variable supplied to the job.

The config should be viewed as a hierachical namespace.  The elements
of the hierachy are separated by periods (.) and where multiple words
are required at a level they should be separated by underscores (_).
Please no StudlyCaps.

For example:
        boot.default_args
"""

__author__ = """Copyright Andy Whitcroft 2006"""

import os

class config(object):
    """The BASIC job configuration

    Properties:
            job
                    The job object for this job
            config
                    The job configuration dictionary
    """

    def __init__(self, job):
        """
                job
                        The job object for this job
        """
        self.job = job
        self.config = {}


    def set(self, name, value):
        if name == "proxy":
            os.environ['http_proxy'] = value
            os.environ['ftp_proxy'] = value

        self.config[name] = value

    def get(self, name):
        if name in self.config:
            return self.config[name]
        else:
            return None
