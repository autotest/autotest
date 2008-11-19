# Copyright Martin J. Bligh, Google Inc 2008
# Released under the GPL v2

"""
This class allows you to communicate with the frontend to submit jobs etc
It is designed for writing more sophisiticated server-side control files that
can recursively add and manage other jobs.

We turn the JSON dictionaries into real objects that are more idiomatic

For docs, see http://autotest//afe/server/noauth/rpc/
http://docs.djangoproject.com/en/dev/ref/models/querysets/#queryset-api
"""

import os, time
import common
from autotest_lib.frontend.afe import rpc_client_lib
from autotest_lib.client.common_lib import utils


def dump_object(header, obj):
    """
    Standard way to print out the frontend objects (eg job, host, acl, label)
    in a human-readable fashion for debugging
    """
    result = header + '\n'
    for key in obj.hash:
        if key == 'afe' or key == 'hash':
            continue
        result += '%20s: %s\n' % (key, obj.hash[key])
    return result


class afe(object):
    """
    AFE class for communicating with the autotest frontend

    All the constructors go in the afe class. 
    Manipulating methods go in the classes themselves
    """
    def __init__(self, user=os.environ.get('LOGNAME'),
                 web_server='http://autotest', print_log=True, debug=False):
        """
        Create a cached instance of a connection to the AFE

            user: username to connect as
            web_server: AFE instance to connect to
            print_log: pring a logging message to stdout on every operation
            debug: print out all RPC traffic
        """
        self.user = user
        self.print_log = print_log
        self.debug = debug
        headers = {'AUTHORIZATION' : self.user}
        rpc_server = web_server + '/afe/server/noauth/rpc/'
        self.proxy = rpc_client_lib.get_proxy(rpc_server, headers=headers)


    def run(self, call, **dargs):
        """
        Make a RPC call to the AFE server
        """
        rpc_call = getattr(self.proxy, call)
        if self.debug:
            print 'DEBUG: %s %s' % (call, dargs)
        return utils.strip_unicode(rpc_call(**dargs))


    def log(self, message):
        if self.print_log:
            print message


    def host_statuses(self, live=None):
        dead_statuses = ['Dead', 'Repair Failed']
        statuses = self.run('get_static_data')['host_statuses']
        if live == True:
            return list(set(statuses) - set(['Dead', 'Repair Failed']))
        if live == False:
            return dead_statuses
        else:
            return statuses


    def get_hosts(self, **dargs):
        hosts = self.run('get_hosts', **dargs)
        return [host(self, h) for h in hosts]


    def create_host(self, hostname, **dargs):
        id = self.run('add_host', **dargs)
        return self.get_hosts(id=id)[0]


    def get_labels(self, **dargs):
        labels = self.run('get_labels', **dargs)
        return [label(self, l) for l in labels]


    def create_label(self, name, **dargs):
        id = self.run('add_label', **dargs)
        return self.get_labels(id=id)[0]


    def get_acls(self, **dargs):
        acls = self.run('get_acl_groups', **dargs)
        return [acl(self, a) for a in acls]


    def create_acl(self, name, **dargs):
        id = self.run('add_acl_group', **dargs)
        return self.get_acls(id=id)[0]


    def get_jobs(self, summary=False, **dargs):
        if summary:
            jobs_data = self.run('get_jobs_summary', **dargs)
        else:
            jobs_data = self.run('get_jobs', **dargs)
        return [job(self, j) for j in jobs_data]


    def get_host_queue_entries(self, **data):
        entries = self.run('get_host_queue_entries', **data)
        return [job_status(self, e) for e in entries]


    def create_job_by_test(self, tests, kernel=None, **dargs):
        """
        Given a test name, fetch the appropriate control file from the server
        and submit it
        """
        results = self.run('generate_control_file', tests=tests, kernel=kernel,
                           use_container=False, do_push_packages=True)
        if results['is_server']:
            dargs['control_type'] = 'Server'
        else:
            dargs['control_type'] = 'Client'
        dargs['dependencies'] = dargs.get('dependencies', []) + \
                                results['dependencies']
        dargs['control_file'] = results['control_file']
        dargs['synch_count'] = results['synch_count']
        return self.create_job(**dargs)


    def create_job(self, control_file, name=' ', priority='Medium',
                control_type='Client', **dargs):
        id = self.run('create_job', name=name, priority=priority,
                 control_file=control_file, control_type=control_type, **dargs)
        return self.get_jobs(id=id)[0]


class rpc_object(object):
    """
    Generic object used to construct python objects from rpc calls
    """
    def __init__(self, afe, hash):
        self.afe = afe
        self.hash = hash
        self.__dict__.update(hash)


    def __str__(self):
        return dump_object(self.__repr__(), self)


class label(rpc_object):
    """
    AFE label object

    Fields:
        name, invalid, platform, kernel_config, id, only_if_needed
    """
    def __repr__(self):
        return 'LABEL: %s' % self.name


    def add_hosts(self, hosts):
        return self.afe.run('label_add_hosts', self.id, hosts)


    def remove_hosts(self, hosts):
        return self.afe.run('label_remove_hosts', self.id, hosts)


class acl(rpc_object):
    """
    AFE acl object

    Fields:
        users, hosts, description, name, id
    """
    def __repr__(self):
        return 'ACL: %s' % self.name


    def add_hosts(self, hosts):
        self.afe.log('Adding hosts %s to ACL %s' % (hosts, self.name))
        return self.afe.run('acl_group_add_hosts', self.id, hosts)


    def remove_hosts(self, hosts):
        self.afe.log('Removing hosts %s from ACL %s' % (hosts, self.name))
        return self.afe.run('acl_group_remove_hosts', self.id, hosts)


class job(rpc_object):
    """
    AFE job object

    Fields:
        name, control_file, control_type, synch_count, reboot_before,
        run_verify, priority, email_list, created_on, dependencies,
        timeout, owner, reboot_after, id
    """
    def __repr__(self):
        return 'JOB: %s' % self.id


class job_status(rpc_object):
    """
    AFE job_status object

    Fields:
        status, complete, deleted, meta_host, host, active, execution_subdir, id
    """
    def __init__(self, afe, hash):
        # This should call super
        self.afe = afe
        self.hash = hash
        self.__dict__.update(hash)
        self.job = job(afe, self.job)
        if self.host:
            self.host = afe.get_hosts(hostname=self.host['hostname'])[0]


    def __repr__(self):
        return 'JOB STATUS: %s-%s' % (self.job.id, self.host.hostname)


class host(rpc_object):
    """
    AFE host object

    Fields:
        status, lock_time, locked_by, locked, hostname, invalid,
        synch_id, labels, platform, protection, dirty, id
    """
    def __repr__(self):
        return 'HOST OBJECT: %s' % self.hostname


    def show(self):
        labels = list(set(self.labels) - set([self.platform]))
        print '%-6s %-7s %-7s %-16s %s' % (self.hostname, self.status,
                                           self.locked, self.platform,
                                           ', '.join(labels))


    def get_acls(self):
        return self.afe.get_acls(hosts__hostname=self.hostname)


    def add_acl(self, acl_name):
        self.afe.log('Adding ACL %s to host %s' % (acl_name, self.hostname))
        return self.afe.run('acl_group_add_hosts', id=acl_name,
                            hosts=[self.hostname])


    def remove_acl(self, acl_name):
        self.afe.log('Removing ACL %s from host %s' % (acl_name, self.hostname))
        return self.afe.run('acl_group_remove_hosts', id=acl_name,
                            hosts=[self.hostname])


    def get_labels(self):
        return self.afe.get_labels(host__hostname__in=[self.hostname])


    def add_labels(self, labels):
        self.afe.log('Adding labels %s to host %s' % (labels, self.hostname))
        return self.afe.run('host_add_labels', id=self.id, labels=labels)


    def remove_labels(self, labels):
        self.afe.log('Removing labels %s from host %s' % (labels,self.hostname))
        return self.afe.run('host_remove_labels', id=self.id, labels=labels)
