#
# Copyright 2008 Google Inc. All Rights Reserved.

"""
The acl module contains the objects and methods used to
manage ACLs in Autotest.

The valid actions are:
add:     adds acl(s), or users or hosts to an ACL
remove:      deletes acl(s), or users or hosts from an ACL
list:    lists acl(s)

The common options are:
--alist / -A: file containing a list of ACLs

See topic_common.py for a High Level Design and Algorithm.

"""

import os, sys
from autotest_lib.cli import topic_common, action_common


class acl(topic_common.atest):
    """ACL class
    atest acl [create|delete|list|add|remove] <options>"""
    usage_action = '[create|delete|list|add|remove]'
    topic = 'acl_group'
    msg_topic = 'ACL'
    msg_items = '<acls>'

    def __init__(self):
        """Add to the parser the options common to all the ACL actions"""
        super(acl, self).__init__()
        self.parser.add_option('-A', '--alist',
                               help='File listing the ACLs',
                               type='string',
                               default=None,
                               metavar='ACL_FLIST')

        self.topic_parse_info = topic_common.item_parse_info(
            attribute_name='acls',
            filename_option='alist',
            use_leftover=True)


    def get_items(self):
        return self.acls


class acl_help(acl):
    """Just here to get the atest logic working.
    Usage is set by its parent"""
    pass


class acl_list(action_common.atest_list, acl):
    """atest acl list [--verbose]
    [--user <users>|--mach <machine>|--alist <file>] [<acls>]"""
    def __init__(self):
        super(acl_list, self).__init__()

        self.parser.add_option('-u', '--user',
                               help='List ACLs containing USER',
                               type='string',
                               metavar='USER')
        self.parser.add_option('-m', '--machine',
                               help='List ACLs containing MACHINE',
                               type='string',
                               metavar='MACHINE')


    def parse(self):
        user_info = topic_common.item_parse_info(attribute_name='users',
                                                 inline_option='user')
        host_info = topic_common.item_parse_info(attribute_name='hosts',
                                                 inline_option='machine')

        (options, leftover) = super(acl_list, self).parse([user_info,
                                                           host_info])

        if ((self.users and (self.hosts or self.acls)) or
            (self.hosts and self.acls)):
            self.invalid_syntax('Only specify one of --user,'
                                '--machine or ACL')

        if len(self.users) > 1:
            self.invalid_syntax('Only specify one <user>')
        if len(self.hosts) > 1:
            self.invalid_syntax('Only specify one <machine>')

        try:
            self.users = self.users[0]
        except IndexError:
            pass

        try:
            self.hosts = self.hosts[0]
        except IndexError:
            pass
        return (options, leftover)


    def execute(self):
        filters = {}
        check_results = {}
        if self.acls:
            filters['name__in'] = self.acls
            check_results['name__in'] = 'name'

        if self.users:
            filters['users__login'] = self.users
            check_results['users__login'] = None

        if self.hosts:
            filters['hosts__hostname'] = self.hosts
            check_results['hosts__hostname'] = None

        return super(acl_list,
                     self).execute(op='get_acl_groups',
                                   filters=filters,
                                   check_results=check_results)


    def output(self, results):
        # If an ACL was specified, always print its details
        if self.acls or self.verbose:
            sublist_keys=('hosts', 'users')
        else:
            sublist_keys=()

        super(acl_list, self).output(results,
                                     keys=('name', 'description'),
                                     sublist_keys=sublist_keys)


class acl_create(action_common.atest_create, acl):
    """atest acl create <acl> --desc <description>"""
    def __init__(self):
        super(acl_create, self).__init__()
        self.parser.add_option('-d', '--desc',
                               help='Creates the ACL with the DESCRIPTION',
                               type='string')
        self.parser.remove_option('--alist')


    def parse(self):
        (options, leftover) = super(acl_create, self).parse(req_items='acls')

        if not options.desc:
            self.invalid_syntax('Must specify a description to create an ACL.')

        self.data_item_key = 'name'
        self.data['description'] = options.desc

        if len(self.acls) > 1:
            self.invalid_syntax('Can only create one ACL at a time')

        return (options, leftover)


class acl_delete(action_common.atest_delete, acl):
    """atest acl delete [<acls> | --alist <file>"""
    pass


class acl_add_or_remove(acl):
    def __init__(self):
        super(acl_add_or_remove, self).__init__()
        # Get the appropriate help for adding or removing.
        words = self.usage_words
        lower_words = tuple(word.lower() for word in words)

        self.parser.add_option('-u', '--user',
                               help='%s USER(s) %s the ACL' % words,
                               type='string',
                               metavar='USER')
        self.parser.add_option('-U', '--ulist',
                               help='File containing users to %s %s '
                               'the ACL' % lower_words,
                               type='string',
                               metavar='USER_FLIST')
        self.parser.add_option('-m', '--machine',
                               help='%s MACHINE(s) %s the ACL' % words,
                               type='string',
                               metavar='MACHINE')
        self.parser.add_option('-M', '--mlist',
                               help='File containing machines to %s %s '
                               'the ACL' % lower_words,
                               type='string',
                               metavar='MACHINE_FLIST')


    def parse(self):
        user_info = topic_common.item_parse_info(attribute_name='users',
                                                 inline_option='user',
                                                 filename_option='ulist')
        host_info = topic_common.item_parse_info(attribute_name='hosts',
                                                 inline_option='machine',
                                                 filename_option='mlist')
        (options, leftover) = super(acl_add_or_remove,
                                    self).parse([user_info, host_info],
                                                req_items='acls')

        if (not getattr(self, 'users', None) and
            not getattr(self, 'hosts', None)):
            self.invalid_syntax('Specify at least one USER or MACHINE')

        return (options, leftover)


class acl_add(action_common.atest_add, acl_add_or_remove):
    """atest acl add <acl> --user <user>|
       --machine <machine>|--mlist <FILE>]"""
    pass


class acl_remove(action_common.atest_remove, acl_add_or_remove):
    """atest acl remove [<acls> | --alist <file>
    --user <user> | --machine <machine> | --mlist <FILE>]"""
    pass
