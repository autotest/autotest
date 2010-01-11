#
# Copyright 2008 Google Inc. All Rights Reserved.

"""
The host module contains the objects and method used to
manage a host in Autotest.

The valid actions are:
create:  adds host(s)
delete:  deletes host(s)
list:    lists host(s)
stat:    displays host(s) information
mod:     modifies host(s)
jobs:    lists all jobs that ran on host(s)

The common options are:
-M|--mlist:   file containing a list of machines


See topic_common.py for a High Level Design and Algorithm.

"""

import os, sys, socket
from autotest_lib.cli import topic_common, action_common
from autotest_lib.client.common_lib import host_protections


class host(topic_common.atest):
    """Host class
    atest host [create|delete|list|stat|mod|jobs] <options>"""
    usage_action = '[create|delete|list|stat|mod|jobs]'
    topic = msg_topic = 'host'
    msg_items = '<hosts>'

    protections = host_protections.Protection.names


    def __init__(self):
        """Add to the parser the options common to all the
        host actions"""
        super(host, self).__init__()

        self.parser.add_option('-M', '--mlist',
                               help='File listing the machines',
                               type='string',
                               default=None,
                               metavar='MACHINE_FLIST')

        self.topic_parse_info = topic_common.item_parse_info(
            attribute_name='hosts',
            filename_option='mlist',
            use_leftover=True)


    def _parse_lock_options(self, options):
        if options.lock and options.unlock:
            self.invalid_syntax('Only specify one of '
                                '--lock and --unlock.')

        if options.lock:
            self.data['locked'] = True
            self.messages.append('Locked host')
        elif options.unlock:
            self.data['locked'] = False
            self.messages.append('Unlocked host')


    def _cleanup_labels(self, labels, platform=None):
        """Removes the platform label from the overall labels"""
        if platform:
            return [label for label in labels
                    if label != platform]
        else:
            try:
                return [label for label in labels
                        if not label['platform']]
            except TypeError:
                # This is a hack - the server will soon
                # do this, so all this code should be removed.
                return labels


    def get_items(self):
        return self.hosts


class host_help(host):
    """Just here to get the atest logic working.
    Usage is set by its parent"""
    pass


class host_list(action_common.atest_list, host):
    """atest host list [--mlist <file>|<hosts>] [--label <label>]
       [--status <status1,status2>] [--acl <ACL>] [--user <user>]"""

    def __init__(self):
        super(host_list, self).__init__()

        self.parser.add_option('-b', '--label',
                               default='',
                               help='Only list hosts with all these labels '
                               '(comma separated)')
        self.parser.add_option('-s', '--status',
                               default='',
                               help='Only list hosts with any of these '
                               'statuses (comma separated)')
        self.parser.add_option('-a', '--acl',
                               default='',
                               help='Only list hosts within this ACL')
        self.parser.add_option('-u', '--user',
                               default='',
                               help='Only list hosts available to this user')
        self.parser.add_option('-N', '--hostnames-only', help='Only return '
                               'hostnames for the machines queried.',
                               action='store_true')
        self.parser.add_option('--locked',
                               default=False,
                               help='Only list locked hosts',
                               action='store_true')
        self.parser.add_option('--unlocked',
                               default=False,
                               help='Only list unlocked hosts',
                               action='store_true')



    def parse(self):
        """Consume the specific options"""
        (options, leftover) = super(host_list, self).parse()
        self.labels = options.label
        self.status = options.status
        self.acl = options.acl
        self.user = options.user
        self.hostnames_only = options.hostnames_only

        if options.locked and options.unlocked:
            self.invalid_syntax('--locked and --unlocked are '
                                'mutually exclusive')
        self.locked = options.locked
        self.unlocked = options.unlocked
        return (options, leftover)


    def execute(self):
        filters = {}
        check_results = {}
        if self.hosts:
            filters['hostname__in'] = self.hosts
            check_results['hostname__in'] = 'hostname'

        if self.labels:
            labels = self.labels.split(',')
            labels = [label.strip() for label in labels if label.strip()]

            if len(labels) == 1:
                # This is needed for labels with wildcards (x86*)
                filters['labels__name__in'] = labels
                check_results['labels__name__in'] = None
            else:
                filters['multiple_labels'] = labels
                check_results['multiple_labels'] = None

        if self.status:
            statuses = self.status.split(',')
            statuses = [status.strip() for status in statuses
                        if status.strip()]

            filters['status__in'] = statuses
            check_results['status__in'] = None

        if self.acl:
            filters['aclgroup__name'] = self.acl
            check_results['aclgroup__name'] = None
        if self.user:
            filters['aclgroup__users__login'] = self.user
            check_results['aclgroup__users__login'] = None

        if self.locked or self.unlocked:
            filters['locked'] = self.locked
            check_results['locked'] = None

        return super(host_list, self).execute(op='get_hosts',
                                              filters=filters,
                                              check_results=check_results)


    def output(self, results):
        if results:
            # Remove the platform from the labels.
            for result in results:
                result['labels'] = self._cleanup_labels(result['labels'],
                                                        result['platform'])
        if self.hostnames_only:
            self.print_list(results, key='hostname')
        else:
            super(host_list, self).output(results, keys=['hostname', 'status',
                                          'locked', 'platform', 'labels'])


class host_stat(host):
    """atest host stat --mlist <file>|<hosts>"""
    usage_action = 'stat'

    def execute(self):
        results = []
        # Convert wildcards into real host stats.
        existing_hosts = []
        for host in self.hosts:
            if host.endswith('*'):
                stats = self.execute_rpc('get_hosts',
                                         hostname__startswith=host.rstrip('*'))
                if len(stats) == 0:
                    self.failure('No hosts matching %s' % host, item=host,
                                 what_failed='Failed to stat')
                    continue
            else:
                stats = self.execute_rpc('get_hosts', hostname=host)
                if len(stats) == 0:
                    self.failure('Unknown host %s' % host, item=host,
                                 what_failed='Failed to stat')
                    continue
            existing_hosts.extend(stats)

        for stat in existing_hosts:
            host = stat['hostname']
            # The host exists, these should succeed
            acls = self.execute_rpc('get_acl_groups', hosts__hostname=host)

            labels = self.execute_rpc('get_labels', host__hostname=host)
            results.append ([[stat], acls, labels])
        return results


    def output(self, results):
        for stats, acls, labels in results:
            print '-'*5
            self.print_fields(stats,
                              keys=['hostname', 'platform',
                                    'status', 'locked', 'locked_by',
                                    'lock_time', 'protection',])
            self.print_by_ids(acls, 'ACLs', line_before=True)
            labels = self._cleanup_labels(labels)
            self.print_by_ids(labels, 'Labels', line_before=True)


class host_jobs(host):
    """atest host jobs [--max-query] --mlist <file>|<hosts>"""
    usage_action = 'jobs'

    def __init__(self):
        super(host_jobs, self).__init__()
        self.parser.add_option('-q', '--max-query',
                               help='Limits the number of results '
                               '(20 by default)',
                               type='int', default=20)


    def parse(self):
        """Consume the specific options"""
        (options, leftover) = super(host_jobs, self).parse()
        self.max_queries = options.max_query
        return (options, leftover)


    def execute(self):
        results = []
        real_hosts = []
        for host in self.hosts:
            if host.endswith('*'):
                stats = self.execute_rpc('get_hosts',
                                         hostname__startswith=host.rstrip('*'))
                if len(stats) == 0:
                    self.failure('No host matching %s' % host, item=host,
                                 what_failed='Failed to stat')
                [real_hosts.append(stat['hostname']) for stat in stats]
            else:
                real_hosts.append(host)

        for host in real_hosts:
            queue_entries = self.execute_rpc('get_host_queue_entries',
                                             host__hostname=host,
                                             query_limit=self.max_queries,
                                             sort_by=['-job__id'])
            jobs = []
            for entry in queue_entries:
                job = {'job_id': entry['job']['id'],
                       'job_owner': entry['job']['owner'],
                       'job_name': entry['job']['name'],
                       'status': entry['status']}
                jobs.append(job)
            results.append((host, jobs))
        return results


    def output(self, results):
        for host, jobs in results:
            print '-'*5
            print 'Hostname: %s' % host
            self.print_table(jobs, keys_header=['job_id',
                                                'job_owner',
                                                'job_name',
                                                'status'])


class host_mod(host):
    """atest host mod --lock|--unlock|--protection
    --mlist <file>|<hosts>"""
    usage_action = 'mod'

    def __init__(self):
        """Add the options specific to the mod action"""
        self.data = {}
        self.messages = []
        super(host_mod, self).__init__()
        self.parser.add_option('-l', '--lock',
                               help='Lock hosts',
                               action='store_true')
        self.parser.add_option('-u', '--unlock',
                               help='Unlock hosts',
                               action='store_true')
        self.parser.add_option('-p', '--protection', type='choice',
                               help=('Set the protection level on a host.  '
                                     'Must be one of: %s' %
                                     ', '.join('"%s"' % p
                                               for p in self.protections)),
                               choices=self.protections)


    def parse(self):
        """Consume the specific options"""
        (options, leftover) = super(host_mod, self).parse()

        self._parse_lock_options(options)

        if options.protection:
            self.data['protection'] = options.protection
            self.messages.append('Protection set to "%s"' % options.protection)

        if len(self.data) == 0:
            self.invalid_syntax('No modification requested')
        return (options, leftover)


    def execute(self):
        successes = []
        for host in self.hosts:
            try:
                res = self.execute_rpc('modify_host', item=host,
                                       id=host, **self.data)
                # TODO: Make the AFE return True or False,
                # especially for lock
                successes.append(host)
            except topic_common.CliError, full_error:
                # Already logged by execute_rpc()
                pass

        return successes


    def output(self, hosts):
        for msg in self.messages:
            self.print_wrapped(msg, hosts)



class host_create(host):
    """atest host create [--lock|--unlock --platform <arch>
    --labels <labels>|--blist <label_file>
    --acls <acls>|--alist <acl_file>
    --protection <protection_type>
    --mlist <mach_file>] <hosts>"""
    usage_action = 'create'

    def __init__(self):
        self.messages = []
        super(host_create, self).__init__()
        self.parser.add_option('-l', '--lock',
                               help='Create the hosts as locked',
                               action='store_true', default=False)
        self.parser.add_option('-u', '--unlock',
                               help='Create the hosts as '
                               'unlocked (default)',
                               action='store_true')
        self.parser.add_option('-t', '--platform',
                               help='Sets the platform label')
        self.parser.add_option('-b', '--labels',
                               help='Comma separated list of labels')
        self.parser.add_option('-B', '--blist',
                               help='File listing the labels',
                               type='string',
                               metavar='LABEL_FLIST')
        self.parser.add_option('-a', '--acls',
                               help='Comma separated list of ACLs')
        self.parser.add_option('-A', '--alist',
                               help='File listing the acls',
                               type='string',
                               metavar='ACL_FLIST')
        self.parser.add_option('-p', '--protection', type='choice',
                               help=('Set the protection level on a host.  '
                                     'Must be one of: %s' %
                                     ', '.join('"%s"' % p
                                               for p in self.protections)),
                               choices=self.protections)


    def parse(self):
        label_info = topic_common.item_parse_info(attribute_name='labels',
                                                 inline_option='labels',
                                                 filename_option='blist')
        acl_info = topic_common.item_parse_info(attribute_name='acls',
                                                inline_option='acls',
                                                filename_option='alist')

        (options, leftover) = super(host_create, self).parse([label_info,
                                                              acl_info],
                                                             req_items='hosts')

        self._parse_lock_options(options)
        self.locked = options.lock
        self.platform = getattr(options, 'platform', None)
        if options.protection:
            self.data['protection'] = options.protection
        return (options, leftover)


    def _execute_add_one_host(self, host):
        # Always add the hosts as locked to avoid the host
        # being picked up by the scheduler before it's ACL'ed
        self.data['locked'] = True
        self.execute_rpc('add_host', hostname=host,
                         status="Ready", **self.data)

        # Now add the platform label
        labels = self.labels[:]
        if self.platform:
            labels.append(self.platform)
        if len (labels):
            self.execute_rpc('host_add_labels', id=host, labels=labels)


    def execute(self):
        # We need to check if these labels & ACLs exist,
        # and create them if not.
        if self.platform:
            self.check_and_create_items('get_labels', 'add_label',
                                        [self.platform],
                                        platform=True)

        if self.labels:
            self.check_and_create_items('get_labels', 'add_label',
                                        self.labels,
                                        platform=False)

        if self.acls:
            self.check_and_create_items('get_acl_groups',
                                        'add_acl_group',
                                        self.acls)

        success = self.site_create_hosts_hook()

        if len(success):
            for acl in self.acls:
                self.execute_rpc('acl_group_add_hosts', id=acl, hosts=success)

            if not self.locked:
                for host in success:
                    self.execute_rpc('modify_host', id=host, locked=False)
        return success


    def site_create_hosts_hook(self):
        success = []
        for host in self.hosts:
            try:
                self._execute_add_one_host(host)
                success.append(host)
            except topic_common.CliError:
                pass

        return success


    def output(self, hosts):
        self.print_wrapped('Added host', hosts)


class host_delete(action_common.atest_delete, host):
    """atest host delete [--mlist <mach_file>] <hosts>"""
    pass
