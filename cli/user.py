#
# Copyright 2008 Google Inc. All Rights Reserved.

"""
The user module contains the objects and methods used to
manage users in Autotest.

The valid action is:
list:    lists user(s)

The common options are:
--ulist / -U: file containing a list of USERs

See topic_common.py for a High Level Design and Algorithm.
"""

import os, sys
from autotest_lib.cli import topic_common, action_common


class user(topic_common.atest):
    """User class
    atest user list <options>"""
    usage_action = 'list'
    topic = msg_topic = 'user'
    msg_items = '<users>'

    def __init__(self):
        """Add to the parser the options common to all the
        user actions"""
        super(user, self).__init__()

        self.parser.add_option('-U', '--ulist',
                               help='File listing the users',
                               type='string',
                               default=None,
                               metavar='USER_FLIST')

        self.topic_parse_info = topic_common.item_parse_info(
            attribute_name='users',
            filename_option='ulist',
            use_leftover=True)


    def get_items(self):
        return self.users


class user_help(user):
    """Just here to get the atest logic working.
    Usage is set by its parent"""
    pass


class user_list(action_common.atest_list, user):
    """atest user list <user>|--ulist <file>
    [--acl <ACL>|--access_level <n>]"""
    def __init__(self):
        super(user_list, self).__init__()

        self.parser.add_option('-a', '--acl',
                               help='Only list users within this ACL')

        self.parser.add_option('-l', '--access_level',
                               help='Only list users at this access level')


    def parse(self):
        (options, leftover) = super(user_list, self).parse()
        self.acl = options.acl
        self.access_level = options.access_level
        return (options, leftover)


    def execute(self):
        filters = {}
        check_results = {}
        if self.acl:
            filters['aclgroup__name__in'] = [self.acl]
            check_results['aclgroup__name__in'] = None

        if self.access_level:
            filters['access_level__in'] = [self.access_level]
            check_results['access_level__in'] = None

        if self.users:
            filters['login__in'] = self.users
            check_results['login__in'] = 'login'

        return super(user_list, self).execute(op='get_users',
                                              filters=filters,
                                              check_results=check_results)


    def output(self, results):
        if self.verbose:
            keys = ['id', 'login', 'access_level']
        else:
            keys = ['login']

        super(user_list, self).output(results, keys)
