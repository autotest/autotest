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
                    'owner', 'control_type',  'synch_type', 'created_on']

        if self.show_control_file:
            keys.append('control_file')

        super(job_stat, self).output(results, keys)


class job_create(action_common.atest_create, job):
    """atest job create [--priority <Low|Medium|High|Urgent>]
    [--is-synchronous] [--container] [--control-file </path/to/cfile>]
    [--on-server] [--test <test1,test2>] [--kernel <http://kernel>]
    [--mlist </path/to/machinelist>] [--machine <host1 host2 host3>]
    job_name"""
    op_action = 'create'
    msg_items = 'job_name'
    display_ids = True

    def __init__(self):
        super(job_create, self).__init__()
        self.hosts = []
        self.ctrl_file_data = {}
        self.data_item_key = 'name'
        self.parser.add_option('-p', '--priority', help='Job priority (low, '
                               'medium, high, urgent), default=medium',
                               type='choice', choices=('low', 'medium', 'high',
                               'urgent'), default='medium')
        self.parser.add_option('-y', '--synchronous', action='store_true',
                               help='Make the job synchronous',
                               default=False)
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
        self.parser.add_option('-m', '--machine', help='List of machines to '
                               'run on')
        self.parser.add_option('-M', '--mlist',
                               help='File listing machines to use',
                               type='string', metavar='MACHINE_FLIST')
        self.parser.add_option('-e', '--email', help='A comma seperated list '
                               'of email addresses to notify of job completion',
                               default='')


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


    def parse(self):
        flists = [('hosts', 'mlist', 'machine', False),
                  ('jobname', '', '', True)]
        (options, leftover) = self.parse_with_flist(flists,
                                                    req_items='jobname')
        self.data = {}

        if len(self.hosts) == 0:
            self.invalid_syntax('Must specify at least one host')
        if not options.control_file and not options.test:
            self.invalid_syntax('Must specify either --test or --control-file'
                                ' to create a job.')
        if options.control_file and options.test:
            self.invalid_syntax('Can only specify one of --control-file or '
                                '--test, not both.')
        if options.container and options.server:
            self.invalid_syntax('Containers (--container) can only be added to'
                                ' client side jobs.')
        if options.control_file:
            if options.kernel:
                self.invalid_syntax('Use --kernel only in conjunction with '
                                    '--test, not --control-file.')
            if options.container:
                self.invalid_syntax('Containers (--container) can only be added'
                                    ' with --test, not --control-file.')
            try:
                self.data['control_file'] = open(options.control_file).read()
            except IOError:
                self.generic_error('Unable to read from specified '
                                   'control-file: %s' % options.control_file)

        if options.priority:
            self.data['priority'] = options.priority.capitalize()

        if len(self.jobname) > 1:
            self.invalid_syntax('Too many arguments specified, only expected '
                                'to receive job name: %s' % self.jobname)
        self.jobname = self.jobname[0]
        self.data['name'] = self.jobname

        (self.data['hosts'],
         self.data['meta_hosts']) = self.parse_hosts(self.hosts)


        self.data['email_list'] = options.email
        self.data['is_synchronous'] = options.synchronous
        if options.server:
            self.data['control_type'] = 'Server'
        else:
            self.data['control_type'] = 'Client'

        if options.test:
            if options.server or options.synchronous:
                self.invalid_syntax('Must specify a control file (--control-'
                                    'file) for jobs that are synchronous or '
                                    'server jobs.')
            self.ctrl_file_data = {'tests': options.test.split(',')}
            if options.kernel:
                self.ctrl_file_data['kernel'] = options.kernel
                self.ctrl_file_data['do_push_packages'] = True
            self.ctrl_file_data['use_container'] = options.container

        # TODO: add support for manually specifying dependencies, when this is
        # added to the frontend as well
        self.data['dependencies'] = []

        return (options, leftover)


    def execute(self):
        if self.ctrl_file_data:
            if self.ctrl_file_data.has_key('kernel'):
                socket.setdefaulttimeout(topic_common.UPLOAD_SOCKET_TIMEOUT)
                print 'Uploading Kernel: this may take a while...',

            cf_info = self.execute_rpc(op='generate_control_file',
                                        item=self.jobname,
                                        **self.ctrl_file_data)

            if self.ctrl_file_data.has_key('kernel'):
                print 'Done'
                socket.setdefaulttimeout(topic_common.DEFAULT_SOCKET_TIMEOUT)
            self.data['control_file'] = cf_info['control_file']
            self.data['is_synchronous'] = cf_info['is_synchronous']
            if cf_info['is_server']:
                self.data['control_type'] = 'Server'
            else:
                self.data['control_type'] = 'Client'
            self.data['dependencies'] = cf_info['dependencies']
        return super(job_create, self).execute()


    def get_items(self):
        return [self.jobname]


class job_abort(job, action_common.atest_delete):
    """atest job abort <job(s)>"""
    usage_action = op_action = 'abort'
    msg_done = 'Aborted'

    def parse(self):
        (options, leftover) = self.parse_with_flist([('jobids', '', '', True)],
                                                    req_items='jobids')


    def get_items(self):
        return self.jobids
