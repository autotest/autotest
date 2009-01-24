#
# Copyright 2008 Google Inc. All Rights Reserved.

"""
The job module contains the objects and methods used to
manage jobs in Autotest.

The valid actions are:
list:    lists job(s)
create:  create a job
abort:   abort job(s)
stat:    detailed listing of job(s)

The common options are:

See topic_common.py for a High Level Design and Algorithm.
"""

import getpass, os, pwd, re, socket, sys
from autotest_lib.cli import topic_common, action_common


class job(topic_common.atest):
    """Job class
    atest job [create|list|stat|abort] <options>"""
    usage_action = '[create|list|stat|abort]'
    topic = msg_topic = 'job'
    msg_items = '<job_ids>'


    def _convert_status(self, results):
        for result in results:
            total = sum(result['status_counts'].values())
            status = ['%s:%s(%.1f%%)' % (key, val, 100.0*float(val)/total)
                      for key, val in result['status_counts'].iteritems()]
            status.sort()
            result['status_counts'] = ', '.join(status)


class job_help(job):
    """Just here to get the atest logic working.
    Usage is set by its parent"""
    pass


class job_list_stat(action_common.atest_list, job):
    def __split_jobs_between_ids_names(self):
        job_ids = []
        job_names = []

        # Sort between job IDs and names
        for job_id in self.jobs:
            if job_id.isdigit():
                job_ids.append(job_id)
            else:
                job_names.append(job_id)
        return (job_ids, job_names)


    def execute_on_ids_and_names(self, op, filters={},
                                 check_results={'id__in': 'id',
                                                'name__in': 'id'},
                                 tag_id='id__in', tag_name='name__in'):
        if not self.jobs:
            # Want everything
            return super(job_list_stat, self).execute(op=op, filters=filters)

        all_jobs = []
        (job_ids, job_names) = self.__split_jobs_between_ids_names()

        for items, tag in [(job_ids, tag_id),
                          (job_names, tag_name)]:
            if items:
                new_filters = filters.copy()
                new_filters[tag] = items
                jobs = super(job_list_stat,
                             self).execute(op=op,
                                           filters=new_filters,
                                           check_results=check_results)
                all_jobs.extend(jobs)

        return all_jobs


class job_list(job_list_stat):
    """atest job list [<jobs>] [--all] [--running] [--user <username>]"""
    def __init__(self):
        super(job_list, self).__init__()
        self.parser.add_option('-a', '--all', help='List jobs for all '
                               'users.', action='store_true', default=False)
        self.parser.add_option('-r', '--running', help='List only running '
                               'jobs', action='store_true')
        self.parser.add_option('-u', '--user', help='List jobs for given '
                               'user', type='string')


    def parse(self):
        (options, leftover) = self.parse_with_flist([('jobs', '', '', True)],
                                                    None)
        self.all = options.all
        self.data['running'] = options.running
        if options.user:
            if options.all:
                self.invalid_syntax('Only specify --all or --user, not both.')
            else:
                self.data['owner'] = options.user
        elif not options.all and not self.jobs:
            self.data['owner'] = getpass.getuser()

        return (options, leftover)


    def execute(self):
        return self.execute_on_ids_and_names(op='get_jobs_summary',
                                             filters=self.data)


    def output(self, results):
        keys = ['id', 'owner', 'name', 'status_counts']
        if self.verbose:
            keys.extend(['priority', 'control_type', 'created_on'])
        self._convert_status(results)
        super(job_list, self).output(results, keys)



class job_stat(job_list_stat):
    """atest job stat <job>"""
    usage_action = 'stat'

    def __init__(self):
        super(job_stat, self).__init__()
        self.parser.add_option('-f', '--control-file',
                               help='Display the control file',
                               action='store_true', default=False)


    def parse(self):
        (options, leftover) = self.parse_with_flist(flists=[('jobs', '', '',
                                                             True)],
                                                    req_items='jobs')
        if not self.jobs:
            self.invalid_syntax('Must specify at least one job.')

        self.show_control_file = options.control_file

        return (options, leftover)


    def _merge_results(self, summary, qes):
        hosts_status = {}
        for qe in qes:
            if qe['host']:
                job_id = qe['job']['id']
                hostname = qe['host']['hostname']
                hosts_status.setdefault(job_id,
                                        {}).setdefault(qe['status'],
                                                       []).append(hostname)

        for job in summary:
            job_id = job['id']
            if hosts_status.has_key(job_id):
                this_job = hosts_status[job_id]
                host_per_status = ['%s:%s' %(status, ','.join(host))
                                   for status, host in this_job.iteritems()]
                job['hosts_status'] = ', '.join(host_per_status)
            else:
                job['hosts_status'] = ''
        return summary


    def execute(self):
        summary = self.execute_on_ids_and_names(op='get_jobs_summary')

        # Get the real hostnames
        qes = self.execute_on_ids_and_names(op='get_host_queue_entries',
                                            check_results={},
                                            tag_id='job__in',
                                            tag_name='job__name__in')

        self._convert_status(summary)

        return self._merge_results(summary, qes)


    def output(self, results):
        if not self.verbose:
            keys = ['id', 'name', 'priority', 'status_counts', 'hosts_status']
        else:
            keys = ['id', 'name', 'priority', 'status_counts', 'hosts_status',
                    'owner', 'control_type',  'synch_count', 'created_on',
                    'run_verify', 'reboot_before', 'reboot_after']

        if self.show_control_file:
            keys.append('control_file')

        super(job_stat, self).output(results, keys)


class job_create(action_common.atest_create, job):
    """atest job create [--priority <Low|Medium|High|Urgent>]
    [--synch_count] [--container] [--control-file </path/to/cfile>]
    [--on-server] [--test <test1,test2>] [--kernel <http://kernel>]
    [--mlist </path/to/machinelist>] [--machine <host1 host2 host3>]
    [--labels <labels this job is dependent on>]
    [--reboot_before <option>] [--reboot_after <option>]
    [--noverify] [--timeout <timeout>]
    job_name

    Creating a job is rather different from the other create operations,
    so it only uses the __init__() and output() from its superclass.
    """
    op_action = 'create'
    msg_items = 'job_name'

    def __init__(self):
        super(job_create, self).__init__()
        self.hosts = []
        self.ctrl_file_data = {}
        self.data_item_key = 'name'
        self.parser.add_option('-p', '--priority', help='Job priority (low, '
                               'medium, high, urgent), default=medium',
                               type='choice', choices=('low', 'medium', 'high',
                               'urgent'), default='medium')
        self.parser.add_option('-y', '--synch_count', type=int,
                               help='Number of machines to use per autoserv '
                                    'execution')
        self.parser.add_option('-c', '--container', help='Run this client job '
                               'in a container', action='store_true',
                               default=False)
        self.parser.add_option('-f', '--control-file',
                               help='use this control file', metavar='FILE')
        self.parser.add_option('-s', '--server',
                               help='This is server-side job',
                               action='store_true', default=False)
        self.parser.add_option('-t', '--test',
                               help='List of tests to run')
        self.parser.add_option('-k', '--kernel', help='Install kernel from this'
                               ' URL before beginning job')
        self.parser.add_option('-b', '--labels', help='Comma separated list of '
                               'labels this job is dependent on.', default='')
        self.parser.add_option('-m', '--machine', help='List of machines to '
                               'run on')
        self.parser.add_option('-M', '--mlist',
                               help='File listing machines to use',
                               type='string', metavar='MACHINE_FLIST')
        self.parser.add_option('-e', '--email', help='A comma seperated list '
                               'of email addresses to notify of job completion',
                               default='')
        self.parser.add_option('-B', '--reboot_before',
                               help='Whether or not to reboot the machine '
                                    'before the job (never/if dirty/always)',
                               type='choice',
                               choices=('never', 'if dirty', 'always'))
        self.parser.add_option('-a', '--reboot_after',
                               help='Whether or not to reboot the machine '
                                    'after the job (never/if all tests passed/'
                                    'always)',
                               type='choice',
                               choices=('never', 'if all tests passed',
                                        'always'))
        self.parser.add_option('-l', '--clone', help='Clone an existing job.  '
                               'This will discard all other options except '
                               '--reuse-hosts.', default=False,
                               metavar='JOB_ID')
        self.parser.add_option('-r', '--reuse-hosts', help='Use the exact same '
                               'hosts as cloned job.  Only for use with '
                               '--clone.', action='store_true', default=False)
        self.parser.add_option('-n', '--noverify',
                               help='Do not run verify for job',
                               default=False, action='store_true')
        self.parser.add_option('-o', '--timeout', help='Job timeout in hours.',
                               metavar='TIMEOUT')


    def parse(self):
        flists = [('hosts', 'mlist', 'machine', False),
                  ('jobname', '', '', True)]
        (options, leftover) = self.parse_with_flist(flists,
                                                    req_items='jobname')
        self.data = {}
        if len(self.jobname) > 1:
            self.invalid_syntax('Too many arguments specified, only expected '
                                'to receive job name: %s' % self.jobname)
        self.jobname = self.jobname[0]

        if options.reuse_hosts and not options.clone:
            self.invalid_syntax('--reuse-hosts only to be used with --clone.')
        # If cloning skip parse, parsing is done in execute
        self.clone_id = options.clone
        if options.clone:
            self.op_action = 'clone'
            self.msg_items = 'jobid'
            self.reuse_hosts = options.reuse_hosts
            return (options, leftover)

        if len(self.hosts) == 0:
            self.invalid_syntax('Must specify at least one machine (-m or -M).')
        if not options.control_file and not options.test:
            self.invalid_syntax('Must specify either --test or --control-file'
                                ' to create a job.')
        if options.control_file and options.test:
            self.invalid_syntax('Can only specify one of --control-file or '
                                '--test, not both.')
        if options.container and options.server:
            self.invalid_syntax('Containers (--container) can only be added to'
                                ' client side jobs.')
        if options.container:
            self.ctrl_file_data['use_container'] = options.container
        if options.kernel:
            self.ctrl_file_data['kernel'] = options.kernel
            self.ctrl_file_data['do_push_packages'] = True
        if options.control_file:
            try:
                control_file_f = open(options.control_file)
                try:
                    control_file_data = control_file_f.read()
                finally:
                    control_file_f.close()
            except IOError:
                self.generic_error('Unable to read from specified '
                                   'control-file: %s' % options.control_file)
            if options.kernel:
                if options.server:
                    self.invalid_syntax(
                            'A control file and a kernel may only be specified'
                            ' together on client side jobs.')
                # execute() will pass this to the AFE server to wrap this
                # control file up to include the kernel installation steps.
                self.ctrl_file_data['client_control_file'] = control_file_data
            else:
                self.data['control_file'] = control_file_data
        if options.test:
            if options.server:
                self.invalid_syntax('If you specify tests, then the '
                                    'client/server setting is implicit and '
                                    'cannot be overriden.')
            tests = [t.strip() for t in options.test.split(',') if t.strip()]
            self.ctrl_file_data['tests'] = tests


        if options.priority:
            self.data['priority'] = options.priority.capitalize()
        if options.reboot_before:
            self.data['reboot_before'] = options.reboot_before.capitalize()
        if options.reboot_after:
            self.data['reboot_after'] = options.reboot_after.capitalize()
        if options.noverify:
            self.data['run_verify'] = False
        if options.timeout:
            self.data['timeout'] = options.timeout

        self.data['name'] = self.jobname

        (self.data['hosts'],
         self.data['meta_hosts']) = self.parse_hosts(self.hosts)

        deps = options.labels.split(',')
        deps = [dep.strip() for dep in deps if dep.strip()]
        self.data['dependencies'] = deps

        self.data['email_list'] = options.email
        if options.synch_count:
            self.data['synch_count'] = options.synch_count
        if options.server:
            self.data['control_type'] = 'Server'
        else:
            self.data['control_type'] = 'Client'

        return (options, leftover)


    def execute(self):
        if self.ctrl_file_data:
            uploading_kernel = 'kernel' in self.ctrl_file_data
            if uploading_kernel:
                socket.setdefaulttimeout(topic_common.UPLOAD_SOCKET_TIMEOUT)
                print 'Uploading Kernel: this may take a while...',
                sys.stdout.flush()
            try:
                cf_info = self.execute_rpc(op='generate_control_file',
                                           item=self.jobname,
                                           **self.ctrl_file_data)
            finally:
                if uploading_kernel:
                    socket.setdefaulttimeout(
                            topic_common.DEFAULT_SOCKET_TIMEOUT)
            if uploading_kernel:
                print 'Done'
            self.data['control_file'] = cf_info['control_file']
            if 'synch_count' not in self.data:
                self.data['synch_count'] = cf_info['synch_count']
            if cf_info['is_server']:
                self.data['control_type'] = 'Server'
            else:
                self.data['control_type'] = 'Client'

            # Get the union of the 2 sets of dependencies
            deps = set(self.data['dependencies'])
            deps = sorted(deps.union(cf_info['dependencies']))
            self.data['dependencies'] = list(deps)

        if 'synch_count' not in self.data:
            self.data['synch_count'] = 1

        if self.clone_id:
            clone_info = self.execute_rpc(op='get_info_for_clone',
                                          id=self.clone_id,
                                          preserve_metahosts=self.reuse_hosts)
            self.data = clone_info['job']

            # Remove fields from clone data that cannot be reused
            unused_fields = ('name', 'created_on', 'id', 'owner')
            for field in unused_fields:
                del self.data[field]

            # Keyword args cannot be unicode strings
            for key, val in self.data.iteritems():
                del self.data[key]
                self.data[str(key)] = val

            # Convert host list from clone info that can be used for job_create
            host_list = []
            if clone_info['meta_host_counts']:
                # Creates a dictionary of meta_hosts, e.g.
                # {u'label1': 3, u'label2': 2, u'label3': 5}
                meta_hosts = clone_info['meta_host_counts']
                # Create a list of formatted metahosts, e.g.
                # [u'3*label1', u'2*label2', u'5*label3']
                meta_host_list = ['%s*%s' % (str(val), key) for key,val in
                                  meta_hosts.items()]
                host_list.extend(meta_host_list)
            if clone_info['hosts']:
                # Creates a list of hosts, e.g. [u'host1', u'host2']
                hosts = [host['hostname'] for host in clone_info['hosts']]
                host_list.extend(hosts)

            (self.data['hosts'],
             self.data['meta_hosts']) = self.parse_hosts(host_list)
            self.data['name'] = self.jobname

        socket.setdefaulttimeout(topic_common.LIST_SOCKET_TIMEOUT)
        # This RPC takes a while when there are lots of hosts.
        # We don't set it back to default because it's the last RPC.

        socket.setdefaulttimeout(topic_common.LIST_SOCKET_TIMEOUT)
        # This RPC takes a while when there are lots of hosts.
        # We don't set it back to default because it's the last RPC.
        job_id = self.execute_rpc(op='create_job', **self.data)
        return ['%s (id %s)' % (self.jobname, job_id)]


    def get_items(self):
        return [self.jobname]


class job_abort(job, action_common.atest_delete):
    """atest job abort <job(s)>"""
    usage_action = op_action = 'abort'
    msg_done = 'Aborted'

    def parse(self):
        (options, leftover) = self.parse_with_flist([('jobids', '', '', True)],
                                                    req_items='jobids')


    def execute(self):
        data = {'job__id__in': self.jobids}
        self.execute_rpc(op='abort_host_queue_entries', **data)
        print 'Aborting jobs: %s' % ', '.join(self.jobids)


    def get_items(self):
        return self.jobids
