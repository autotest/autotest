#
# Copyright 2008 Google Inc. All Rights Reserved.

"""This module contains the common behavior of some actions

Operations on ACLs or labels are very similar, so are creations and
deletions. The following classes provide the common handling.

In these case, the class inheritance is, taking the command
'atest label create' as an example:

                  atest
                 /     \
                /       \
               /         \
         atest_create   label
               \         /
                \       /
                 \     /
               label_create


For 'atest label add':

                  atest
                 /     \
                /       \
               /         \
               |       label
               |         |
               |         |
               |         |
         atest_add   label_add_or_remove
               \         /
                \       /
                 \     /
               label_add



"""

import re, socket, types
from autotest_lib.cli import topic_common


#
# List action
#
class atest_list(topic_common.atest):
    """atest <topic> list"""
    usage_action = 'list'


    def _convert_wildcard(self, old_key, new_key,
                          value, filters, check_results):
        filters[new_key] = value.rstrip('*')
        check_results[new_key] = None
        del filters[old_key]
        del check_results[old_key]


    def _convert_name_wildcard(self, key, value, filters, check_results):
        if value.endswith('*'):
            # Could be __name, __login, __hostname
            new_key = key + '__startswith'
            self._convert_wildcard(key, new_key, value, filters, check_results)


    def _convert_in_wildcard(self, key, value, filters, check_results):
        if value.endswith('*'):
            assert key.endswith('__in'), 'Key %s does not end with __in' % key
            new_key = key.replace('__in', '__startswith', 1)
            self._convert_wildcard(key, new_key, value, filters, check_results)


    def check_for_wildcard(self, filters, check_results):
        """Check if there is a wilcard (only * for the moment)
        and replace the request appropriately"""
        for (key, values) in filters.iteritems():
            if isinstance(values, types.StringTypes):
                self._convert_name_wildcard(key, values,
                                            filters, check_results)
                continue

            if isinstance(values, types.ListType):
                if len(values) == 1:
                    self._convert_in_wildcard(key, values[0],
                                              filters, check_results)
                    continue

                for value in values:
                    if value.endswith('*'):
                        # Can only be a wildcard if it is by itelf
                        self.invalid_syntax('Cannot mix wilcards and items')


    def execute(self, op, filters={}, check_results={}):
        """Generic list execute:
        If no filters where specified, list all the items.  If
        some specific items where asked for, filter on those:
        check_results has the same keys than filters.  If only
        one filter is set, we use the key from check_result to
        print the error"""
        self.check_for_wildcard(filters, check_results)

        results = self.execute_rpc(op, **filters)

        for dbkey in filters.keys():
            if not check_results.get(dbkey, None):
                # Don't want to check the results
                # for this key
                continue

            if len(results) >= len(filters[dbkey]):
                continue

            # Some bad items
            field = check_results[dbkey]
            # The filtering for the job is on the ID which is an int.
            # Convert it as the jobids from the CLI args are strings.
            good = set(str(result[field]) for result in results)
            self.invalid_arg('Unknown %s(s): \n' % self.msg_topic,
                             ', '.join(set(filters[dbkey]) - good))
        return results


    def output(self, results, keys, sublist_keys=[]):
        self.print_table(results, keys, sublist_keys)


#
# Creation & Deletion of a topic (ACL, label, user)
#
class atest_create_or_delete(topic_common.atest):
    """atest <topic> [create|delete]
    To subclass this, you must define:
                         Example          Comment
    self.topic           'acl_group'
    self.op_action       'delete'        Action to remove a 'topic'
    self.data            {}              Additional args for the topic
                                         creation/deletion
    self.msg_topic:      'ACL'           The printable version of the topic.
    self.msg_done:       'Deleted'       The printable version of the action.
    """
    def execute(self):
        handled = []

        # Create or Delete the <topic> altogether
        op = '%s_%s' % (self.op_action, self.topic)
        for item in self.get_items():
            try:
                self.data[self.data_item_key] = item
                new_id = self.execute_rpc(op, item=item, **self.data)
                handled.append(item)
            except topic_common.CliError:
                pass
        return handled


    def output(self, results):
        if results:
            results = ["'%s'" % r for r in results]
            self.print_wrapped("%s %s" % (self.msg_done, self.msg_topic),
                               results)


class atest_create(atest_create_or_delete):
    usage_action = 'create'
    op_action = 'add'
    msg_done = 'Created'


class atest_delete(atest_create_or_delete):
    data_item_key = 'id'
    usage_action = op_action = 'delete'
    msg_done = 'Deleted'


#
# Adding or Removing things (users, hosts or labels) from a topic
# (ACL, Label or AtomicGroup)
#
class atest_add_or_remove(topic_common.atest):
    """atest <topic> [add|remove]
    To subclass this, you must define these attributes:
                       Example             Comment
    topic              'acl_group'
    op_action          'remove'            Action for adding users/hosts
    add_remove_things  {'users': 'user'}   Dict of things to try add/removing.
                                           Keys are the attribute names.  Values
                                           are the word to print for an
                                           individual item of such a value.
    """

    add_remove_things = {'users': 'user', 'hosts': 'host'}  # Original behavior


    def _add_remove_uh_to_topic(self, item, what):
        """Adds the 'what' (such as users or hosts) to the 'item'"""
        uhs = getattr(self, what)
        if len(uhs) == 0:
            # To skip the try/else
            raise AttributeError
        op = '%s_%s_%s' % (self.topic, self.op_action, what)
        try:
            self.execute_rpc(op=op,                       # The opcode
                             **{'id': item, what: uhs})   # The data
            setattr(self, 'good_%s' % what, uhs)
        except topic_common.CliError, full_error:
            bad_uhs = self.parse_json_exception(full_error)
            good_uhs = list(set(uhs) - set(bad_uhs))
            if bad_uhs and good_uhs:
                self.execute_rpc(op=op,
                                 **{'id': item, what: good_uhs})
                setattr(self, 'good_%s' % what, good_uhs)
            else:
                raise


    def execute(self):
        """Adds or removes things (users, hosts, etc.) from a topic, e.g.:

        Add hosts to labels:
          self.topic = 'label'
          self.op_action = 'add'
          self.add_remove_things = {'users': 'user', 'hosts': 'host'}
          self.get_items() = The labels/ACLs that the hosts
                             should be added to.

        Returns:
          A dictionary of lists of things added successfully using the same
          keys as self.add_remove_things.
        """
        oks = {}
        for item in self.get_items():
            # FIXME(gps):
            # This reverse sorting is only here to avoid breaking many
            # existing extremely fragile unittests which depend on the
            # exact order of the calls made below.  'users' must be run
            # before 'hosts'.
            plurals = reversed(sorted(self.add_remove_things.keys()))
            for what in plurals:
                try:
                    self._add_remove_uh_to_topic(item, what)
                except AttributeError:
                    pass
                except topic_common.CliError, err:
                    # The error was already logged by
                    # self.failure()
                    pass
                else:
                    oks.setdefault(item, []).append(what)

        results = {}
        for thing in self.add_remove_things:
            things_ok = [item for item, what in oks.items() if thing in what]
            results[thing] = things_ok

        return results


    def output(self, results):
        for thing, single_thing in self.add_remove_things.iteritems():
            # Enclose each of the elements in a single quote.
            things_ok = ["'%s'" % t for t in results[thing]]
            if things_ok:
                self.print_wrapped("%s %s %s %s" % (self.msg_done,
                                                    self.msg_topic,
                                                    ', '.join(things_ok),
                                                    single_thing),
                                   getattr(self, 'good_%s' % thing))


class atest_add(atest_add_or_remove):
    usage_action = op_action = 'add'
    msg_done = 'Added to'
    usage_words = ('Add', 'to')


class atest_remove(atest_add_or_remove):
    usage_action = op_action = 'remove'
    msg_done = 'Removed from'
    usage_words = ('Remove', 'from')
