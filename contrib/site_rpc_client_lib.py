"""
This module provides site-local authorization headers for Apache.
It asks the end-user for a password, rather than assuming no password
is necessary.
To actually use this, put it in the cli/ directory.

:author: Nishanth Aravamudan <nacc@linux.vnet.ibm.com>
"""

import getpass
import os
import base64


def authorization_headers(username, server):
    """
    Ask the user for their password, rather than assuming they don't
    need one.

    :return: A dictionary of authorization headers to pass in to get_proxy().
    """
    if not username:
        if 'AUTOTEST_USER' in os.environ:
            username = os.environ['AUTOTEST_USER']
        else:
            username = getpass.getuser()
    password = getpass.getpass('Enter the password for %s: ' % username)
    base64string = base64.encodestring('%s:%s' % (username, password))[:-1]
    return {'AUTHORIZATION': 'Basic %s' % base64string}
