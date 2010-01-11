#
# Copyright 2008 Google Inc. All Rights Reserved.

"""
The label module contains the objects and methods used to
manage labels in Autotest.

The valid actions are:
add:     adds label(s), or hosts to an LABEL
remove:      deletes label(s), or hosts from an LABEL
list:    lists label(s)

The common options are:
--blist / -B: file containing a list of LABELs

See topic_common.py for a High Level Design and Algorithm.
"""

import os, sys
from autotest_lib.cli import topic_common, action_common


class label(topic_common.atest):
    """Label class
    atest label [create|delete|list|add|remove] <options>"""
    usage_action = '[create|delete|list|add|remove]'
    topic = msg_topic = 'label'
    msg_items = '<labels>'

    def __init__(self):
        """Add to the parser the options common to all the
        label actions"""
        super(label, self).__init__()

        self.parser.add_option('-B', '--blist',
                               help='File listing the labels',
                               type='string',
                               default=None,
                               metavar='LABEL_FLIST')

        self.topic_parse_info = topic_common.item_parse_info(
            attribute_name='labels',
            filename_option='blist',
            use_leftover=True)


    def get_items(self):
        return self.labels


class label_help(label):
    """Just here to get the atest logic working.
    Usage is set by its parent"""
    pass


class label_list(action_common.atest_list, label):
    """atest label list [--platform] [--all] [--atomicgroup]
    [--valid-only] [--machine <machine>]
    [--blist <file>] [<labels>]"""
    def __init__(self):
        super(label_list, self).__init__()

        self.parser.add_option('-t', '--platform-only',
                               help='Display only platform labels',
                               action='store_true')

        self.parser.add_option('-d', '--valid-only',
                               help='Display only valid labels',
                               action='store_true')

        self.parser.add_option('-a', '--all',
                               help=('Display both normal & '
                                     'platform labels'),
                               action='store_true')

        self.parser.add_option('--atomicgroup',
                               help=('Display only atomic group labels '
                                     'along with the atomic group name.'),
                               action='store_true')

        self.parser.add_option('-m', '--machine',
                               help='List LABELs of MACHINE',
                               type='string',
                               metavar='MACHINE')


    def parse(self):
        host_info = topic_common.item_parse_info(attribute_name='hosts',
                                                 inline_option='machine')
        (options, leftover) = super(label_list, self).parse([host_info])

        exclusives = [options.all, options.platform_only, options.atomicgroup]
        if exclusives.count(True) > 1:
            self.invalid_syntax('Only specify one of --all,'
                                '--platform, --atomicgroup')

        if len(self.hosts) > 1:
            self.invalid_syntax(('Only one machine name allowed. '
                                '''Use '%s host list %s' '''
                                 'instead.') %
                                (sys.argv[0], ','.join(self.hosts)))
        self.all = options.all
        self.atomicgroup = options.atomicgroup
        self.platform_only = options.platform_only
        self.valid_only = options.valid_only
        return (options, leftover)


    def execute(self):
        filters = {}
        check_results = {}
        if self.hosts:
            filters['host__hostname__in'] = self.hosts
            check_results['host__hostname__in'] = None

        if self.labels:
            filters['name__in'] = self.labels
            check_results['name__in'] = 'name'

        return super(label_list, self).execute(op='get_labels',
                                               filters=filters,
                                               check_results=check_results)


    def output(self, results):
        if self.valid_only:
            results = [label for label in results
                       if not label['invalid']]

        if self.platform_only:
            results = [label for label in results
                       if label['platform']]
            keys = ['name', 'invalid']
        elif self.atomicgroup:
            results = [label for label in results
                       if label['atomic_group']]
            keys = ['name', 'atomic_group.name', 'invalid']
        elif not self.all:
            results = [label for label in results
                       if not label['platform']]
            keys = ['name', 'only_if_needed', 'invalid']
        else:
            keys = ['name', 'platform', 'only_if_needed', 'invalid']

        super(label_list, self).output(results, keys)


class label_create(action_common.atest_create, label):
    """atest label create <labels>|--blist <file> --platform"""
    def __init__(self):
        super(label_create, self).__init__()
        self.parser.add_option('-t', '--platform',
                               help='To create this label as a platform',
                               default=False,
                               action='store_true')
        self.parser.add_option('-o', '--only_if_needed',
                               help='To mark the label as "only use if needed',
                               default=False,
                               action='store_true')


    def parse(self):
        (options, leftover) = super(label_create,
                                    self).parse(req_items='labels')
        self.data_item_key = 'name'
        self.data['platform'] = options.platform
        self.data['only_if_needed'] = options.only_if_needed
        return (options, leftover)


class label_delete(action_common.atest_delete, label):
    """atest label delete <labels>|--blist <file>"""
    pass



class label_add_or_remove(label):
    def __init__(self):
        super(label_add_or_remove, self).__init__()
        lower_words = tuple(word.lower() for word in self.usage_words)
        self.parser.add_option('-m', '--machine',
                               help=('%s MACHINE(s) %s the LABEL' %
                                     self.usage_words),
                               type='string',
                               metavar='MACHINE')
        self.parser.add_option('-M', '--mlist',
                               help='File containing machines to %s %s '
                               'the LABEL' % lower_words,
                               type='string',
                               metavar='MACHINE_FLIST')


    def parse(self):
        host_info = topic_common.item_parse_info(attribute_name='hosts',
                                                 inline_option='machine',
                                                 filename_option='mlist')
        (options, leftover) = super(label_add_or_remove,
                                    self).parse([host_info],
                                                req_items='labels')

        if not getattr(self, 'hosts', None):
            self.invalid_syntax('%s %s requires at least one host' %
                                (self.msg_topic,
                                 self.usage_action))
        return (options, leftover)


class label_add(action_common.atest_add, label_add_or_remove):
    """atest label add <labels>|--blist <file>
    --platform [--machine <machine>] [--mlist <file>]"""
    pass


class label_remove(action_common.atest_remove, label_add_or_remove):
    """atest label remove <labels>|--blist <file>
     [--machine <machine>] [--mlist <file>]"""
    pass
