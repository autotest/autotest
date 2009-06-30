
"""
The atomicgroup module contains the objects and methods used to
manage atomic groups in Autotest.

The valid actions are:
create:  Create a new atomic group.
delete:  Delete (invalidate) an existing atomic group.
list:    Lists atomic groups.
add:     Adds labels to an atomic group.
remove:  Removes labels from an atomic group.

See topic_common.py for a High Level Design and Algorithm.
"""

import os, sys
from autotest_lib.cli import topic_common, action_common

class atomicgroup(topic_common.atest):
    """
    Atomic group class

    atest atomicgroup [create|delete|list|add|remove] <options>
    """
    usage_action = '[create|delete|list|add|remove]'
    topic = 'atomic_group'
    msg_topic = 'atomicgroup'
    msg_items = '<atomicgroups>'


    def __init__(self):
        super(atomicgroup, self).__init__()
        self.parser.add_option('-G', '--glist',
                               help='File listing the ATOMIC GROUPs',
                               type='string', default=None,
                               metavar='ATOMIC_GROUP_FLIST')

        self.topic_parse_info = topic_common.item_parse_info(
            attribute_name='atomicgroups',
            filename_option='glist',
            use_leftover=True)


    def get_items(self):
        return self.atomicgroups


class atomicgroup_help(atomicgroup):
    """Just to get the atest logic working.  Usage is set by its parent."""
    pass


class atomicgroup_list(action_common.atest_list, atomicgroup):
    """atest atomicgroup list [--show-invalid]"""
    def __init__(self):
        super(atomicgroup_list, self).__init__()
        self.parser.add_option('-d', '--show-invalid',
                               help='Don\'t hide invalid atomic groups.',
                               action='store_true')


    def parse(self):
        options, leftover = super(atomicgroup_list, self).parse()
        self.show_invalid = options.show_invalid
        return options, leftover


    def execute(self):
        return super(atomicgroup_list, self).execute(op='get_atomic_groups')


    def output(self, results):
        if not self.show_invalid:
            results = [atomicgroup for atomicgroup in results
                       if not atomicgroup['invalid']]

        keys = ['name', 'description', 'max_number_of_machines', 'invalid']
        super(atomicgroup_list, self).output(results, keys)


class atomicgroup_create(action_common.atest_create, atomicgroup):
    def __init__(self):
        super(atomicgroup_create, self).__init__()
        self.parser.add_option('-n', '--max_number_of_machines',
                               help='Maximum # of machines for this group.',
                               type='int', default=None)
        self.parser.add_option('-d', '--description',
                               help='Description of this atomic group.',
                               type='string', default='')


    def parse(self):
        options, leftover = super(atomicgroup_create, self).parse()
        self.data_item_key = 'name'
        self.data['description'] = options.description
        self.data['max_number_of_machines'] = options.max_number_of_machines
        return options, leftover


class atomicgroup_delete(action_common.atest_delete, atomicgroup):
    """atest atomicgroup delete <atomicgroup>"""
    pass


class atomicgroup_add_or_remove(atomicgroup):

    def __init__(self):
        super(atomicgroup_add_or_remove, self).__init__()
        # .add_remove_things is used by action_common.atest_add_or_remove.
        self.add_remove_things = {'labels': 'label'}
        lower_words = tuple(word.lower() for word in self.usage_words)
        self.parser.add_option('-l', '--label',
                               help=('%s LABELS(s) %s the ATOMIC GROUP.' %
                                     self.usage_words),
                               type='string',
                               metavar='LABEL')
        self.parser.add_option('-L', '--label_list',
                               help='File containing LABELs to %s %s '
                               'the ATOMIC GROUP.' % lower_words,
                               type='string',
                               metavar='LABEL_FLIST')


    def parse(self):
        label_info = topic_common.item_parse_info(attribute_name='labels',
                                                  inline_option='label',
                                                  filename_option='label_list')

        options, leftover = super(atomicgroup_add_or_remove,
                                  self).parse([label_info],
                                              req_items='atomicgroups')
        if not getattr(self, 'labels', None):
            self.invalid_syntax('%s %s requires at least one label' %
                                (self.msg_topic,
                                 self.usage_action))
        return options, leftover


class atomicgroup_add(action_common.atest_add, atomicgroup_add_or_remove):
    """atest atomicgroup add <atomicgroup>
     [--label <label>] [--label_list <file>]"""
    pass


class atomicgroup_remove(action_common.atest_remove, atomicgroup_add_or_remove):
    """atest atomicgroup remove <atomicgroup>
     [--label <label>] [--label_list <file>]"""
    pass
