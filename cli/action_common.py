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
            assert(key.endswith('__in'))
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

        socket.setdefaulttimeout(topic_common.LIST_SOCKET_TIMEOUT)
        results = self.execute_rpc(op, **filters)

        for dbkey in filters.keys():
            if not check_results.get(dbkey, None):
                # Don't want to check the results
                # for this key
                continue

            if len(results) == len(filters[dbkey]):
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
            self.print_wrapped ("%s %s" % (self.msg_done, self.msg_topic),
                                results)


class atest_create(atest_create_or_delete):
    usage_action = 'create'
    op_action = 'add'
    msg_done = 'Created'

    def parse_hosts(self, args):
        """ Parses the arguments to generate a list of hosts and meta_hosts
        A host is a regular name, a meta_host is n*label or *label.
        These can be mixed on the CLI, and separated by either commas or
        spaces, e.g.: 5*Machine_Label host0 5*Machine_Label2,host2 """

        hosts = []
        meta_hosts = []

        for arg in args:
            for host in arg.split(','):
                if re.match('^[0-9]+[*]', host):
                    num, host = host.split('*', 1)
                    meta_hosts += int(num) * [host]
                elif re.match('^[*](\w*)', host):
                    meta_hosts += [re.match('^[*](\w*)', host).group(1)]
                elif host != '':
                    # Real hostname
                    hosts.append(host)

        return (hosts, meta_hosts)


class atest_delete(atest_create_or_delete):
    data_item_key = 'id'
    usage_action = op_action = 'delete'
    msg_done = 'Deleted'


#
# Adding or Removing users or hosts from a topic (ACL or label)
#
class atest_add_or_remove(topic_common.atest):
    """atest <topic> [add|remove]
    To subclass this, you must define:
                       Example          Comment
    self.topic         'acl_group'
    self.op_action     'remove'         Action for adding users/hosts
    """

    def _add_remove_uh_to_topic(self, item, what):
        """Adds the 'what' (users or hosts) to the 'item'"""
        uhs = getattr(self, what)
        if len(uhs) == 0:
            # To skip the try/else
            raise AttributeError
        op = '%s_%s_%s' % (self.topic, self.op_action, what)
        self.execute_rpc(op=op,                                 # The opcode
                         item='%s (%s)' %(item, ','.join(uhs)), # The error
                         **{'id': item, what: uhs})             # The data


    def execute(self):
        """Adds or removes users or hosts from a topic, e.g.:
        add hosts to labels:
          self.topic = 'label'
          self.op_action = 'add'
          self.get_items() = the labels that the hosts
                             should be added to"""
        oks = {}
        for item in self.get_items():
            for what in ['users', 'hosts']:
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

        users_ok = [item for (item, what) in oks.items() if 'users' in what]
        hosts_ok = [item for (item, what) in oks.items() if 'hosts' in what]

        return (users_ok, hosts_ok)


    def output(self, results):
        (users_ok, hosts_ok) = results
        if users_ok:
            self.print_wrapped("%s %s %s user" %
                               (self.msg_done,
                                self.msg_topic,
                                ', '.join(users_ok)),
                               self.users)

        if hosts_ok:
            self.print_wrapped("%s %s %s host" %
                               (self.msg_done,
                                self.msg_topic,
                                ', '.join(hosts_ok)),
                               self.hosts)


class atest_add(atest_add_or_remove):
    usage_action = op_action = 'add'
    msg_done = 'Added to'
    usage_words = ('Add', 'to')


class atest_remove(atest_add_or_remove):
    usage_action = op_action = 'remove'
    msg_done = 'Removed from'
    usage_words = ('Remove', 'from')
